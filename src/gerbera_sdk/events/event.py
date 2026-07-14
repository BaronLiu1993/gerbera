from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
import uuid

from gerbera_sdk.events.buffer import Buffer


@dataclass
class Event:
    event_type: str
    microcontroller_id: str
    event_name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    streamable: bool = False
    table_name: str | None = None
    buffer: Buffer | None = None
    responses: Queue[dict[str, str]] = field(default_factory=Queue)

    def __post_init__(self) -> None:
        if self.streamable and self.buffer is None:
            if self.table_name is None:
                raise RuntimeError("Streamable event requires a table_name")

            self.buffer = Buffer(table_name=self.table_name)

    def perform_work(self, payload: dict[str, str]) -> dict[str, str] | None:
        normalized_payload = dict(payload)

        if self.streamable:
            if self.buffer is None:
                raise RuntimeError("Streamable event requires a buffer")

            normalized_payload["created_at"] = datetime.now(timezone.utc)
            self.buffer.write(normalized_payload)
            return None

        self.responses.put(normalized_payload)
        return normalized_payload

    def flush(self) -> list[dict[str, str]]:
        if self.buffer is None:
            return []

        return self.buffer.flush()

    def clear_responses(self) -> None:
        while True:
            try:
                self.responses.get_nowait()
                self.responses.task_done()
            except Empty:
                return

    def wait_for_response(self, timeout: float = 3.0) -> dict[str, str]:
        try:
            return self.responses.get(timeout=timeout)
        except Empty as exc:
            raise TimeoutError(f"Timed out waiting for event response: {self.id}") from exc
