import importlib.util
from pathlib import Path
import subprocess
import time

import psycopg
from psycopg import sql
import secrets

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import ColumnSpec
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.gerbera_runtime import GerberaRuntime

# Docker config values from Github registry
GERBERA_IMAGE = "ghcr.io/baronliu1993/gerbera:latest"
POSTGRES_IMAGE = "ghcr.io/baronliu1993/gerbera-postgres:latest"
SANDBOX_IMAGE = "ghcr.io/baronliu1993/gerbera-sandbox:latest"
NETWORK = "gerbera"
POSTGRES_CONTAINER = "gerbera-postgres"
HARNESS_CONTAINER = "gerbera-harness"
POSTGRES_VOLUME = "gerbera_postgres_data"


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

# Local Run
def run_local_server(
    gerbera_writer_password: str,
    database_host: str,
    database_port: int,
    hardware_system: HardwareSystem,
) -> None:
    GerberaRuntime.run(
        hardware_system,
        transport="http",
        host="127.0.0.1",
        port=8001,
        database_host=database_host,
        database_port=database_port,
        database_password=gerbera_writer_password,
    )

def run_firmware_setup(hardware_system: HardwareSystem) -> None: 
    GerberaRuntime.setup(
        hardware_system,
        install_dependencies=True,
        flash_firmware=True,
    )

def setup_local_container(
    gerbera_admin_password: str,
    gerbera_schema_password: str,
    gerbera_writer_password: str,
    gerbera_reader_password: str,
):
    subprocess.run(["docker", "pull", GERBERA_IMAGE], check=True)
    subprocess.run(["docker", "pull", POSTGRES_IMAGE], check=True)
    subprocess.run(["docker", "network", "create", NETWORK], check=False)
    subprocess.run(["docker", "volume", "create", POSTGRES_VOLUME], check=True)
    subprocess.run(["docker", "rm", "-f", POSTGRES_CONTAINER], check=False)
    subprocess.run(["docker", "rm", "-f", HARNESS_CONTAINER], check=False)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            POSTGRES_CONTAINER,
            "--network",
            NETWORK,
            "-p",
            "6432:5432",
            "-e",
            "POSTGRES_DB=gerbera",
            "-e",
            "POSTGRES_USER=gerbera_admin",
            "-e",
            f"POSTGRES_PASSWORD={gerbera_admin_password}",
            "-e",
            f"GERBERA_SCHEMA_PASSWORD={gerbera_schema_password}",
            "-e",
            f"GERBERA_WRITER_PASSWORD={gerbera_writer_password}",
            "-e",
            f"GERBERA_READER_PASSWORD={gerbera_reader_password}",
            "-v",
            f"{POSTGRES_VOLUME}:/var/lib/postgresql/data",
            POSTGRES_IMAGE,
        ],
        check=True,
    )

    wait_for_database(
        host="127.0.0.1",
        port=6432,
        dbname="gerbera",
        user="gerbera_admin",
        password=gerbera_admin_password,
    )

def pull_sandbox_image() -> None:
    subprocess.run(["docker", "pull", SANDBOX_IMAGE], check=True)


def run_harness_container(
    gerbera_schema_password: str,
    gerbera_writer_password: str,
    gerbera_reader_password: str,
    provider: str,
    mcp_url: str,
    api_key: str,
):
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            HARNESS_CONTAINER,
            "--network",
            NETWORK,
            "-p",
            "8000:8000",
            "-e",
            f"GERBERA_DATABASE_HOST={POSTGRES_CONTAINER}",
            "-e",
            "GERBERA_DATABASE_PORT=5432",
            "-e",
            "GERBERA_DATABASE_NAME=gerbera",
            "-e",
            "GERBERA_SCHEMA_USER=gerbera_schema_owner",
            "-e",
            f"GERBERA_SCHEMA_PASSWORD={gerbera_schema_password}",
            "-e",
            "GERBERA_WRITER_USER=gerbera_writer",
            "-e",
            f"GERBERA_WRITER_PASSWORD={gerbera_writer_password}",
            "-e",
            "GERBERA_READER_USER=gerbera_reader",
            "-e",
            f"GERBERA_READER_PASSWORD={gerbera_reader_password}",
            "-e",
            f"GERBERA_MCP_URL={mcp_url}",
            "-e",
            f"PROVIDER={provider}",
            "-e",
            f"API_KEY={api_key}",
            GERBERA_IMAGE,
        ],
        check=True,
    )


def wait_for_database(
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
) -> None:
    for _ in range(30):
        try:
            with psycopg.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
            ):
                return
        except psycopg.OperationalError:
            time.sleep(1)

    raise RuntimeError("Postgres did not start")


def load_hardware_system(config: dict):
    entry_point = Path(config["entry_point"])
    hardware_name = config["hardware_name"]
    spec = importlib.util.spec_from_file_location("gerbera_user_app", entry_point)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, hardware_name)

def create_stream_tables(
    hardware_system: HardwareSystem,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
) -> None:
    with psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    ) as connection:
        with connection.cursor() as cursor:
            for microcontroller in hardware_system.microcontrollers:
                for device_connection in microcontroller.connections:
                    builder = get_device_builder(device_connection.component_type)
                    contract = builder.build_stream_contract(device_connection)

                    if contract is None:
                        continue

                    columns = [
                        column_definition(name, spec)
                        for name, spec in contract.schema.items()
                    ]
                    cursor.execute(
                        sql.SQL(
                            "CREATE TABLE IF NOT EXISTS {table} ({columns})"
                        ).format(
                            table=sql.Identifier(contract.table_name),
                            columns=sql.SQL(", ").join(columns),
                        )
                    )

                    for column_name, column_spec in contract.schema.items():
                        if column_spec.idx:
                            cursor.execute(
                                sql.SQL(
                                    "CREATE INDEX IF NOT EXISTS {index} "
                                    "ON {table} ({column})"
                                ).format(
                                    index=sql.Identifier(
                                        f"{contract.table_name}_{column_name}_idx"
                                    ),
                                    table=sql.Identifier(contract.table_name),
                                    column=sql.Identifier(column_name),
                                )
                            )


def column_definition(name: str, spec: ColumnSpec) -> sql.Composed:
    parts = [
        sql.Identifier(name),
        sql.SQL(spec.type.value),
    ]

    if spec.sql_suffix:
        parts.append(sql.SQL(spec.sql_suffix))

    if spec.default:
        parts.append(sql.SQL(f"DEFAULT {spec.default}"))

    if spec.primary_key:
        parts.append(sql.SQL("PRIMARY KEY"))

    if not spec.nullable:
        parts.append(sql.SQL("NOT NULL"))

    return sql.SQL(" ").join(parts)
