from dataclasses import dataclass, field

import psycopg
from psycopg import sql

from gerbera_sdk.config.database_config import DATABASE_NAME, load_table_sql
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
        for board in hardware.microcontrollers:
            for connection in board.connections:
                if connection.supports_streaming:
                    with self.connect("gerbera_schema_owner", self.schema_password) as database:
                        table_name = connection.connection_id
                        template = load_table_sql(connection.component_type)
                        database.execute(
                            sql.SQL(template).format(
                                table=sql.Identifier(table_name),
                                value_index=sql.Identifier(f"{table_name}_value_idx"),
                                created_at_index=sql.Identifier(f"{table_name}_created_at_idx"),
                            )
                        )

    def write_batch(self, table_name: str, batch: list[dict[str, str]]) -> None:
        if not batch:
            return

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
