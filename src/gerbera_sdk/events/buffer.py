from dataclasses import dataclass, field

from gerbera_sdk.events.event_worker import event_worker


@dataclass
class Buffer:
    buffer_id: str
    event_id: str
    table_name: str
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
        event_worker.write_to_db(self.table_name, batch)
        return batch
