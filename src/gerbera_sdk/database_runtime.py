import time
from dataclasses import dataclass, field

import psycopg
from psycopg import sql

from gerbera_sdk.firmware.devices.config_schema import ColumnConfig
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem

DATABASE_STARTUP_TIMEOUT_SECONDS = 60
DATABASE_RETRY_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    writer_password: str = field(repr=False)
    schema_password: str | None = field(default=None, repr=False)


def column_definition(name: str, specification: ColumnConfig) -> sql.Composed:
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
class DatabaseRuntime:
    hardware_system: HardwareSystem
    settings: DatabaseSettings

    def connect(self, user: str, password: str) -> psycopg.Connection:
        deadline = time.monotonic() + DATABASE_STARTUP_TIMEOUT_SECONDS
        while True:
            try:
                return psycopg.connect(
                    host=self.settings.host,
                    port=self.settings.port,
                    dbname="gerbera",
                    user=user,
                    password=password,
                    connect_timeout=2,
                )
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "SDK storage did not become available during startup"
                    ) from None
                time.sleep(DATABASE_RETRY_INTERVAL_SECONDS)

    def prepare(self) -> None:
        contracts = [
            contract
            for board in self.hardware_system.microcontrollers
            for connection in board.connections
            if (
                contract := get_device_builder(
                    connection.component_type
                ).build_stream_contract(connection)
            )
            is not None
        ]
        if not contracts:
            return
        if self.settings.schema_password is None:
            raise RuntimeError(
                "SDK stream schema preparation requires GERBERA_SCHEMA_PASSWORD"
            )
        with self.connect(
            "gerbera_schema_owner", self.settings.schema_password
        ) as connection:
            with connection.cursor() as cursor:
                for contract in contracts:
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
                    for name, spec in contract.schema.items():
                        if spec.idx:
                            cursor.execute(
                                sql.SQL(
                                    "CREATE INDEX IF NOT EXISTS {index} ON {table} ({column})"
                                ).format(
                                    index=sql.Identifier(
                                        f"{contract.table_name}_{name}_idx"
                                    ),
                                    table=sql.Identifier(contract.table_name),
                                    column=sql.Identifier(name),
                                )
                            )
        with self.connect(
            "gerbera_writer", self.settings.writer_password
        ) as connection:
            connection.execute("SELECT 1")

    def write_batch(self, table_name: str, batch: list[dict[str, str]]) -> None:
        if not batch:
            raise ValueError(f"Database write payload is empty: {table_name}")

        keys = batch[0].keys()
        query = sql.SQL(
            "INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(", ").join(sql.Placeholder(key) for key in keys),
        )
        with psycopg.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname="gerbera",
            user="gerbera_writer",
            password=self.settings.writer_password,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, batch)
