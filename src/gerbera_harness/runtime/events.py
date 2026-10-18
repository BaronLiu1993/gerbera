from dataclasses import dataclass, field

from gerbera_harness.runtime.contracts import EventHandler
from gerbera_harness.runtime.state_machine.schemas import WorkflowEvent


@dataclass
class EventPublisher:
    handlers: tuple[EventHandler, ...] = ()
    sequence: int = field(default=0, init=False)
    handler_failures: int = field(default=0, init=False)

    async def publish(self, event: WorkflowEvent) -> None:
        self.sequence += 1
        event = event.model_copy(update={"id": self.sequence}, deep=True)
        for handler in self.handlers:
            try:
                await handler(event.model_copy(deep=True))
            except Exception:
                self.handler_failures += 1
