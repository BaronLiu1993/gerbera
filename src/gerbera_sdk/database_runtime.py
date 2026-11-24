import time
from dataclasses import dataclass, field
from importlib.resources import files

import psycopg
from psycopg import sql

from gerbera_sdk.config.database_tables import DATABASE_NAME, TABLE_CONFIGURATION
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass(frozen=True)
class DatabaseRuntime:
    host: str
    port: int
    writer_password: str = field(repr=False)
    schema_password: str | None = field(default=None, repr=False)

    def connect(self, user: str, password: str) -> psycopg.Connection:
        while True:
            try:
                return psycopg.connect(
                    host=self.host,
                    port=self.port,
                    dbname=DATABASE_NAME,
                    user=user,
                    password=password,
                    connect_timeout=2,
                )
            except psycopg.OperationalError:
                raise TimeoutError(
                    "SDK storage did not become available during startup"
                ) from None

    def prepare(self, hardware: HardwareSystem) -> None:
        if self.schema_password is None:
            raise RuntimeError(
                "SDK stream schema preparation requires GERBERA_SCHEMA_PASSWORD"
            )

        sql_directory = files("gerbera_sdk.config").joinpath("sql")

        for board in hardware.microcontrollers:
            for connection in board.connections:
                if connection.supports_streaming:
                    with self.connect("gerbera_schema_owner", self.schema_password) as database:
                        filename = TABLE_CONFIGURATION[connection.component_type]
                        table_name = connection.connection_id
                        template = sql_directory.joinpath(filename).read_text(encoding="utf-8")
                        database.execute(
                            sql.SQL(template).format(
                                table=sql.Identifier(table_name),
                                value_index=sql.Identifier(f"{table_name}_value_idx"),
                                created_at_index=sql.Identifier(f"{table_name}_created_at_idx"),
                            )
                        )

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
            host=self.host,
            port=self.port,
            dbname=DATABASE_NAME,
            user="gerbera_writer",
            password=self.writer_password,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, batch)
