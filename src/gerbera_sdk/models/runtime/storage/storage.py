from dataclasses import dataclass
import time

import psycopg
from psycopg import sql

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import ColumnSpec
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan

DATABASE_STARTUP_TIMEOUT_SECONDS = 60
DATABASE_RETRY_INTERVAL_SECONDS = 0.5


def connect_database(database: Database) -> psycopg.Connection:
    deadline = time.monotonic() + DATABASE_STARTUP_TIMEOUT_SECONDS
    while True:
        try:
            return psycopg.connect(database.dsn(), connect_timeout=2)
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise TimeoutError("SDK storage did not become available during startup") from None
            time.sleep(DATABASE_RETRY_INTERVAL_SECONDS)


def column_definition(name: str, specification: ColumnSpec) -> sql.Composed:
    parts = [sql.Identifier(name), sql.SQL(specification.type.value)]
    if specification.sql_suffix:
        parts.append(sql.SQL(specification.sql_suffix))
    if specification.default:
        parts.append(sql.SQL(f"DEFAULT {specification.default}"))
    if specification.primary_key:
        parts.append(sql.SQL("PRIMARY KEY"))
    if not specification.nullable:
        parts.append(sql.SQL("NOT NULL"))
    return sql.SQL(" ").join(parts)


@dataclass(frozen=True)
class RuntimeStorage:
    plan: HardwarePlan
    writer: Database
    schema_owner: Database | None = None

    def prepare(self) -> None:
        contracts = [
            contract for board in self.plan.boards for connection in board.connections
            if (contract := get_device_builder(connection.component_type).build_stream_contract(connection))
            is not None
        ]
        if not contracts:
            return
        if self.schema_owner is None:
            raise RuntimeError("SDK stream schema preparation requires GERBERA_SCHEMA_PASSWORD")
        with connect_database(self.schema_owner) as connection:
            with connection.cursor() as cursor:
                for contract in contracts:
                    columns = [column_definition(name, spec) for name, spec in contract.schema.items()]
                    cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {table} ({columns})").format(
                        table=sql.Identifier(contract.table_name), columns=sql.SQL(", ").join(columns),
                    ))
                    for name, spec in contract.schema.items():
                        if spec.idx:
                            cursor.execute(sql.SQL(
                                "CREATE INDEX IF NOT EXISTS {index} ON {table} ({column})"
                            ).format(
                                index=sql.Identifier(f"{contract.table_name}_{name}_idx"),
                                table=sql.Identifier(contract.table_name), column=sql.Identifier(name),
                            ))
        with connect_database(self.writer) as connection:
            connection.execute("SELECT 1")
