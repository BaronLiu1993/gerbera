from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class Buffer:
    table_name: str
    event_worker: EventWorker = field(repr=False)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_size: int = 50
    items: list[dict[str, str]] = field(default_factory=list)

    def write(self, payload: dict[str, str]) -> bool:
        self.items.append(dict(payload))
        if self._should_flush():
            self.flush()
        return True

    def _should_flush(self) -> bool:
        return len(self.items) >= self.max_size

    def flush(self) -> list[dict[str, str]]:
        batch = list(self.items)
        if not batch:
            return []

        self.items.clear()
        self.event_worker.write_to_db(self.table_name, batch)
        return batch
