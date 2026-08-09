from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class Event:
    event_type: str
    microcontroller_id: str
    event_name: str
    streamable: bool
    table_name: str
    event_worker: EventWorker
    event_store: object # Object payload if MCP event, read from there to get it 

    @cached_property
    def buffer(self) -> Buffer:
        return Buffer(
            table_name=self.table_name,
            event_worker=self.event_worker,
        )

    @cached_property
    def event_key(self):
        return (
            self.event_type,
            self.microcontroller_id,
            self.event_name,
        )

    def perform_work(self, payload: dict[str, str]) -> None:
        normalized_payload = dict(payload)
        normalized_payload["created_at"] = datetime.now(timezone.utc)

        if self.streamable:
            self.buffer.write(normalized_payload)
            return

        self.event_store = normalized_payload

    # For flushing the partial records manually for just this one
    def flush(self) -> list[dict[str, str]]:
        return self.buffer.flush()
