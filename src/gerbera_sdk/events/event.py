from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event_schema import EventKey


@dataclass
class Event:
    event_key: EventKey
    buffer: Buffer
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    @property
    def streamable(self) -> bool:
        return self.event_key.event_type == "STREAM"

    def stream_data(self, payload: dict[str, str]) -> None:
        if self.streamable and len(payload) != 1:
            raise ValueError("Stream payload must contain exactly one field")
        normalized_payload = dict(payload)

        if self.streamable:
            stream_value = next(iter(normalized_payload.values()))
            stream_payload = {"value": stream_value}
            stream_payload["created_at"] = datetime.now(timezone.utc)
            self.buffer.write(stream_payload)
            return

    def flush(self) -> list[dict[str, str]]:
        return self.buffer.flush()
