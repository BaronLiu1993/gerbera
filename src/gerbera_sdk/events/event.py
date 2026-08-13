from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
import threading

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class Event:
    event_type: str
    microcontroller_id: str
    event_name: str
    connection_name: str
    component_type: str
    streamable: bool
    table_name: str
    event_worker: EventWorker
    latest_val: dict[str, str] | None = None
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

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

        with self.lock:
            self.latest_val = normalized_payload

        if self.streamable:
            stream_value = next(iter(normalized_payload.values()), "")
            stream_payload = {"value": stream_value}
            stream_payload["created_at"] = datetime.now(timezone.utc)
            self.buffer.write(stream_payload)
            return
        
    def read_latest(self) -> dict[str, str] | None:
        with self.lock:
            return self.latest_val

    def flush(self) -> list[dict[str, str]]:
        return self.buffer.flush()
