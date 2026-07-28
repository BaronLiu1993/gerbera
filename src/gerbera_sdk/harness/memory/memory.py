from dataclasses import dataclass, field
import json
import sqlite3
from gerbera_sdk.harness.memory.event import Event


# No need for sqlite we can use postgres
@dataclass
class Memory:
    @classmethod

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
