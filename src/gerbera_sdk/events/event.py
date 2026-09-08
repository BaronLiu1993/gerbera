from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading

from gerbera_sdk.events.buffer import Buffer


@dataclass
class Event:
    event_type: str
    microcontroller_id: str
    event_name: str
    connection_name: str
    component_type: str
    streamable: bool
    table_name: str
    buffer: Buffer
    event_key: str
    latest_val: dict[str, str] | None = None
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
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
