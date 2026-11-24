from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event_schema import EventKey


@dataclass
class Event:
    event_key: EventKey
    buffer: Buffer | None = None
    payload_fields: dict[str, str | None] = field(default_factory=dict)

    @property
    def streamable(self) -> bool:
        return self.event_key.event_type == "STREAM"

    def stream_data(self, payload: Mapping[str, str]) -> None:
        if self.buffer is None:
            return
        if len(payload) != 1:
            raise ValueError("Stream payload must contain exactly one field")

        self.buffer.write_to_buffer({
            "value": next(iter(payload.values())),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def flush(self) -> None:
        if self.buffer is not None:
            self.buffer.flush_to_worker()
