from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gerbera_sdk.harness.memory.event import Event


DATABASE_PATH = Path(__file__).resolve().with_name("memory.db")
SCHEMA_PATH = Path(__file__).resolve().with_name("schema.sql")


@dataclass
class Memory:
    connection: sqlite3.Connection = field(repr=False)

    @classmethod
    def connect(cls) -> Memory:
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA_PATH.read_text())
        return cls(connection=connection)

    def append_event(self, state: str, event: Event) -> None:
        timestamp = event.timestamp.isoformat()

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO events_log (
                    id,
                    state,
                    event_type,
                    source_type,
                    payload,
                    timestamp,
                    aggregate_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    state,
                    event.event_type.value,
                    event.source_type.value,
                    json.dumps(event.payload),
                    timestamp,
                    event.session_id,
                ),
            )
