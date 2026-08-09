from __future__ import annotations

from dataclasses import dataclass, field

import psycopg
from psycopg import sql

from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.database import Database


@dataclass
class DatabaseRuntime:
    event_worker: EventWorker
    database: Database
    _started: bool = field(default=False, init=False, repr=False)

    def start(self) -> None:
        self.event_worker.configure_writer(self)
        self.event_worker.start()
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        try:
            self.event_worker.wait_until_idle()
        finally:
            self.event_worker.stop()
            self._started = False

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        if not payload:
            raise ValueError(f"Database write payload is empty: {table_name}")

        keys = payload[0].keys()
        query = sql.SQL(
            "INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(", ").join(sql.Placeholder(key) for key in keys),
        )

        with psycopg.connect(self._dsn(self.database)) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, payload)

    @staticmethod
    def _dsn(database: Database) -> str:
        return (
            f"host={database.host} "
            f"port={database.port} "
            f"dbname={database.databaseName} "
            f"user={database.user} "
            f"password={database.password}"
        )
