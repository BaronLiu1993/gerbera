from dataclasses import dataclass, field
from typing import Protocol
import uuid


class RuleEventHandler(Protocol):
    def perform_work(self, payload: dict[str, str]) -> None:
        pass


@dataclass
class RuleEvent:
    name: str
    handler: RuleEventHandler | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def perform_work(self, payload: dict[str, str]) -> None:
        if self.handler is None:
            return

        self.handler.perform_work(payload)
