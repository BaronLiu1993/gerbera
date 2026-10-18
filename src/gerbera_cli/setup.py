import importlib.util
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time

import httpx
import psycopg
from psycopg import sql

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import ColumnSpec
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_cli.configuration import (
    ProjectConfig,
    ProjectSecrets,
    find_project_config,
)
from gerbera_harness.runtime.project_runtime import StartupStage

GERBERA_IMAGE = "ghcr.io/baronliu1993/gerbera:latest"
POSTGRES_IMAGE = "ghcr.io/baronliu1993/gerbera-postgres:latest"
SANDBOX_IMAGE = "ghcr.io/baronliu1993/gerbera-sandbox:latest"
NETWORK = "gerbera"
POSTGRES_CONTAINER = "gerbera-postgres"
HARNESS_CONTAINER = "gerbera-harness"
POSTGRES_VOLUME = "gerbera_postgres_data"
RUNTIME_PATH = Path(".gerbera/runtime")
SERVER_PID_PATH = RUNTIME_PATH / "server.pid"
LOGS_PATH = Path(".gerbera/logs")
SERVER_LOG_PATH = LOGS_PATH / "server.log"
SERVER_START_TIMEOUT_SECONDS = 30.0


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def run_local_server(
    config: ProjectConfig,
    project_secrets: ProjectSecrets,
    hardware_system: HardwareSystem,
) -> None:
    GerberaRuntime.run(
        hardware_system,
        transport="http",
        host=config.runtime.host,
        port=config.runtime.port,
        database_host=config.runtime.database_host,
        database_port=config.runtime.database_port,
        database_password=project_secrets.gerbera_writer_password,
    )


def run_firmware_setup(hardware_system: HardwareSystem) -> None:
    GerberaRuntime.setup(
        hardware_system,
        install_dependencies=True,
        flash_firmware=True,
    )


def run_forced_firmware_setup(hardware_system: HardwareSystem) -> None:
    GerberaRuntime.bind_connection_microcontroller_ids(hardware_system)
    hardware_plan = GerberaRuntime.validate_hardware(hardware_system)
    GerberaRuntime.install_dependencies(hardware_system)
    Flash.flash_all(hardware_plan)


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


def load_hardware_system(
    config: ProjectConfig | dict,
    config_path: Path | None = None,
):
    if isinstance(config, ProjectConfig):
        entry_point = config.project.entry_point
        hardware_name = config.project.hardware_variable
    else:
        entry_point = Path(config["entry_point"])
        hardware_name = config["hardware_name"]
    spec = importlib.util.spec_from_file_location("gerbera_user_app", entry_point)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Gerbera entry point: {entry_point}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hardware_system = getattr(module, hardware_name)
    if not isinstance(hardware_system, HardwareSystem):
        raise TypeError(
            f"{hardware_name} in {entry_point} must be a HardwareSystem"
        )
    resolved_config_path = config_path or find_project_config()
    for microcontroller in hardware_system.microcontrollers:
        microcontroller.config_path = resolved_config_path
    return hardware_system


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


class LocalProjectServices:
    def __init__(
        self,
        config: ProjectConfig,
        secrets: ProjectSecrets,
        config_path: Path,
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.config_path = config_path
        self.hardware_system = None

    def preflight(self) -> None:
        failures = [
            result for result in self.doctor() if result.startswith("FAIL")
        ]
        if failures:
            raise RuntimeError("Preflight failed:\n" + "\n".join(failures))

    def doctor(self) -> tuple[str, ...]:
        return (
            self.python_check(),
            self.dependency_check("arduino-cli"),
            self.dependency_check("docker"),
            self.docker_check(),
            self.entry_point_check(),
            self.secrets_check(),
        )

    @staticmethod
    def python_check() -> str:
        if sys.version_info[:2] != (3, 12):
            return "FAIL Python: Gerbera requires Python 3.12"
        return "PASS Python: 3.12"

    @staticmethod
    def dependency_check(command: str) -> str:
        if shutil.which(command) is None:
            return f"FAIL {command}: command not found"
        return f"PASS {command}: available"

    @staticmethod
    def docker_check() -> str:
        if shutil.which("docker") is None:
            return "FAIL docker daemon: Docker is not installed"
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return "FAIL docker daemon: not reachable"
        return "PASS docker daemon: reachable"

    def entry_point_check(self) -> str:
        entry_point = self.config.project.entry_point
        if not entry_point.is_file():
            return f"FAIL entry point: file does not exist: {entry_point}"
        return f"PASS entry point: {entry_point}"

    def secrets_check(self) -> str:
        if (self.config.harness.enabled
                and self.config.harness.model_type == "api"
                and not self.secrets.api_key):
            return "FAIL harness credentials: API key is missing"
        if (self.config.harness.enabled and self.config.harness.model is None
                and not Path(".gerbera/harness/harness.json").is_file()):
            return "FAIL harness configuration: model name is missing"
        return "PASS secrets: valid"

    def validate_hardware(self) -> None:
        self.hardware_system = load_hardware_system(
            self.config,
            self.config_path,
        )
        GerberaRuntime.bind_connection_microcontroller_ids(self.hardware_system)
        GerberaRuntime.validate_hardware(self.hardware_system)

    def start_database(self) -> bool:
        if container_running(POSTGRES_CONTAINER):
            return False
        if container_exists(POSTGRES_CONTAINER):
            run_docker("start", POSTGRES_CONTAINER)
            return True
        ensure_docker_resource("network", NETWORK)
        ensure_docker_resource("volume", POSTGRES_VOLUME)
        run_docker("pull", POSTGRES_IMAGE)
        run_docker(
            "run",
            "-d",
            "--name",
            POSTGRES_CONTAINER,
            "--network",
            NETWORK,
            "-p",
            f"{self.config.runtime.database_port}:5432",
            "-e",
            "POSTGRES_DB=gerbera",
            "-e",
            "POSTGRES_USER=gerbera_admin",
            "-e",
            f"POSTGRES_PASSWORD={self.secrets.gerbera_admin_password}",
            "-e",
            f"GERBERA_SCHEMA_PASSWORD={self.secrets.gerbera_schema_password}",
            "-e",
            f"GERBERA_WRITER_PASSWORD={self.secrets.gerbera_writer_password}",
            "-e",
            f"GERBERA_READER_PASSWORD={self.secrets.gerbera_reader_password}",
            "-v",
            f"{POSTGRES_VOLUME}:/var/lib/postgresql/data",
            POSTGRES_IMAGE,
        )
        return True

    def prepare_database(self) -> None:
        if self.hardware_system is None:
            raise RuntimeError("Hardware must be validated before database setup")
        wait_for_database(
            host=self.config.runtime.database_host,
            port=self.config.runtime.database_port,
            dbname="gerbera",
            user="gerbera_admin",
            password=self.secrets.gerbera_admin_password,
        )
        create_stream_tables(
            hardware_system=self.hardware_system,
            host=self.config.runtime.database_host,
            port=self.config.runtime.database_port,
            dbname="gerbera",
            user="gerbera_schema_owner",
            password=self.secrets.gerbera_schema_password,
        )

    def setup_firmware(self) -> None:
        if self.hardware_system is None:
            raise RuntimeError("Hardware must be validated before firmware setup")
        run_firmware_setup(self.hardware_system)

    def start_server(self) -> bool:
        if managed_server_running():
            return False
        ensure_port_available(
            self.config.runtime.host,
            self.config.runtime.port,
        )
        RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        with SERVER_LOG_PATH.open("a") as log_file:
            process = subprocess.Popen(
                [sys.executable, "-m", "gerbera_cli.main", "server"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        SERVER_PID_PATH.write_text(str(process.pid))
        return True

    def wait_for_server(self) -> None:
        deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if port_is_open(
                local_service_host(self.config.runtime.host),
                self.config.runtime.port,
            ):
                return
            if not managed_server_running():
                raise RuntimeError(
                    f"Gerbera server exited during startup. See {SERVER_LOG_PATH}"
                )
            time.sleep(0.25)
        raise TimeoutError(
            f"Gerbera server did not become ready within "
            f"{SERVER_START_TIMEOUT_SECONDS:g} seconds"
        )

    def start_harness(self) -> bool:
        if not self.config.harness.enabled:
            return False
        if container_running(HARNESS_CONTAINER):
            self.wait_for_harness()
            return False
        if container_exists(HARNESS_CONTAINER):
            run_docker("rm", "-f", HARNESS_CONTAINER)
        run_docker("pull", GERBERA_IMAGE)
        run_docker("pull", SANDBOX_IMAGE)
        config_mount = []
        config_directory = Path(".gerbera/harness")
        if (config_directory / "harness.json").is_file():
            config_mount = [
                "-v", f"{config_directory.resolve()}:/app/harness-config:ro",
                "-e", "GERBERA_HARNESS_CONFIG=/app/harness-config/harness.json",
            ]
        run_docker(
            "run",
            "-d",
            "--name",
            HARNESS_CONTAINER,
            "--network",
            NETWORK,
            "--add-host",
            "host.docker.internal:host-gateway",
            *config_mount,
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
            f"GERBERA_SCHEMA_PASSWORD={self.secrets.gerbera_schema_password}",
            "-e",
            "GERBERA_WRITER_USER=gerbera_writer",
            "-e",
            f"GERBERA_WRITER_PASSWORD={self.secrets.gerbera_writer_password}",
            "-e",
            "GERBERA_READER_USER=gerbera_reader",
            "-e",
            f"GERBERA_READER_PASSWORD={self.secrets.gerbera_reader_password}",
            "-e",
            (
                "MCP_URL=http://host.docker.internal:"
                f"{self.config.runtime.port}/mcp"
            ),
            "-e",
            f"PROVIDER={self.config.harness.provider}",
            "-e",
            f"GERBERA_MODEL={self.config.harness.model or ''}",
            "-e",
            f"GERBERA_MODEL_TYPE={self.config.harness.model_type}",
            "-e",
            f"API_KEY={self.secrets.api_key}",
            GERBERA_IMAGE,
        )
        try:
            self.wait_for_harness()
        except BaseException:
            stop_container(HARNESS_CONTAINER)
            raise
        return True

    @staticmethod
    def wait_for_harness() -> None:
        deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
        with httpx.Client(timeout=1.0) as client:
            while time.monotonic() < deadline:
                if not container_running(HARNESS_CONTAINER):
                    raise RuntimeError(
                        "Harness exited during startup. Run 'gerbera logs'."
                    )
                try:
                    response = client.get("http://127.0.0.1:8000/health")
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
        raise TimeoutError("Harness did not become healthy during startup")

    def rollback(self, stages: tuple[StartupStage, ...]) -> None:
        for stage in stages:
            if stage is StartupStage.HARNESS:
                stop_container(HARNESS_CONTAINER)
            elif stage is StartupStage.SERVER:
                stop_managed_server()
            elif stage is StartupStage.DATABASE:
                stop_container(POSTGRES_CONTAINER)

    def stop(self) -> None:
        stop_container(HARNESS_CONTAINER)
        stop_managed_server()
        stop_container(POSTGRES_CONTAINER)

    def status(self) -> dict[str, object]:
        local_host = local_service_host(self.config.runtime.host)
        return {
            "database": container_running(POSTGRES_CONTAINER),
            "server": managed_server_running(),
            "harness": container_running(HARNESS_CONTAINER),
            "mcp_url": (
                f"http://{local_host}:"
                f"{self.config.runtime.port}/mcp"
            ),
            "configured_devices": len(self.config.devices),
        }

    def logs(self, follow: bool) -> None:
        print_server_log()
        for container_name in (POSTGRES_CONTAINER, HARNESS_CONTAINER):
            print_container_log(container_name)
        if follow:
            follow_service_logs()


def run_docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        check=True,
        text=True,
    )


def container_exists(name: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "inspect", name],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def container_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def ensure_docker_resource(resource: str, name: str) -> None:
    inspected = subprocess.run(
        ["docker", resource, "inspect", name],
        capture_output=True,
        check=False,
    )
    if inspected.returncode != 0:
        run_docker(resource, "create", name)


def stop_container(name: str) -> None:
    if container_running(name):
        subprocess.run(["docker", "stop", name], check=True)


def managed_server_running() -> bool:
    if not SERVER_PID_PATH.is_file():
        return False
    try:
        process_id = int(SERVER_PID_PATH.read_text())
        os.kill(process_id, 0)
    except (OSError, ValueError):
        SERVER_PID_PATH.unlink(missing_ok=True)
        return False
    return True


def stop_managed_server() -> None:
    if not managed_server_running():
        return
    process_id = int(SERVER_PID_PATH.read_text())
    terminate_process(process_id, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        terminate_process(process_id, signal.SIGKILL)
    SERVER_PID_PATH.unlink(missing_ok=True)


def terminate_process(process_id: int, termination_signal: int) -> None:
    if hasattr(os, "killpg"):
        os.killpg(process_id, termination_signal)
        return
    os.kill(process_id, termination_signal)


def ensure_port_available(host: str, port: int) -> None:
    if port_is_open(local_service_host(host), port):
        raise RuntimeError(f"Port is already in use: {host}:{port}")


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def local_service_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def print_server_log() -> None:
    if SERVER_LOG_PATH.is_file():
        print(f"==> {SERVER_LOG_PATH} <==")
        print(SERVER_LOG_PATH.read_text(), end="")


def print_container_log(name: str) -> None:
    if not container_exists(name):
        return
    print(f"==> docker:{name} <==")
    subprocess.run(
        ["docker", "logs", "--tail", "100", name],
        check=False,
    )


def follow_service_logs() -> None:
    commands = [
        ["tail", "-n", "100", "-f", str(SERVER_LOG_PATH)],
    ]
    commands.extend(
        ["docker", "logs", "--follow", name]
        for name in (POSTGRES_CONTAINER, HARNESS_CONTAINER)
        if container_exists(name)
    )
    processes = [
        subprocess.Popen(command)
        for command in commands
        if command[0] != "tail" or SERVER_LOG_PATH.is_file()
    ]
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()
