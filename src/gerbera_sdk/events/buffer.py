from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class Buffer:
    table_name: str
    event_worker: EventWorker = field(repr=False)
    max_size: int = 50
    items: list[dict[str, str]] = field(default_factory=list)

    def write(self, payload: dict[str, str]) -> None:
        self.items.append(dict(payload))
        if len(self.items) >= self.max_size:
            self.flush()

    # Flush now, lets call this when server is shutting down
    def flush(self) -> None:
        batch = list(self.items)
        self.items.clear()
        self.event_worker.write_to_db(self.table_name, batch)
        
