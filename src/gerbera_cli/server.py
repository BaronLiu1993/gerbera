import os

import psycopg
from psycopg import sql

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import ColumnSpec
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


def local_server_config(port: str = "8000", host: str = "127.0.0.1") -> dict:
    return {
        "type": "local",
        "connection_url": f"http://{host}:{port}/mcp",
    }


# Ngrok support later:
# def public_server_config(public_endpoint: str) -> dict:
#     return {
#         "type": "ngrok",
#         "connection_url": f"{public_endpoint.rstrip('/')}/mcp",
#     }


def create_stream_tables(hardware_system: HardwareSystem) -> None:
    with psycopg.connect(
        host=os.environ.get("GERBERA_DATABASE_HOST", "127.0.0.1"),
        port=int(os.environ.get("GERBERA_DATABASE_PORT", "6432")),
        dbname=os.environ.get("GERBERA_DATABASE_NAME", "gerbera"),
        user=os.environ.get("GERBERA_SCHEMA_USER", "gerbera_schema_owner"),
        password=os.environ.get("GERBERA_SCHEMA_PASSWORD", "schema_password"),
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
                        sql.SQL("CREATE TABLE IF NOT EXISTS {table} ({columns})").format(
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
