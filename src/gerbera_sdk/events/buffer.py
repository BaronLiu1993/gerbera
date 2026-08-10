from dataclasses import dataclass, field
import threading
import uuid

from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class Buffer:
    table_name: str
    event_worker: EventWorker = field(repr=False)
    max_size: int = 50
    items: list[dict[str, str]] = field(default_factory=list)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def write(self, payload: dict[str, str]) -> None:
        with self.lock:
            self.items.append(dict(payload))
            if len(self.items) >= self.max_size:
                self.flush()

    # Flush now, lets call this when server is shutting down
    def flush(self) -> None:
        with self.lock:
            batch = list(self.items)
            self.items.clear()

        self.event_worker.write_to_db(self.table_name, batch)
        
