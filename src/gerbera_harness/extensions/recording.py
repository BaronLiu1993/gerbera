from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from gerbera_harness.runtime.extensions import HarnessRegistry
from gerbera_harness.runtime.state_machine.schemas import WorkflowEvent


class EventStore(Protocol):
    async def append(self, event: WorkflowEvent) -> None: ...


@dataclass
class MemoryEventStore:
    maximum_events: int = 10_000
    events: deque[WorkflowEvent] = field(default_factory=deque)

    async def append(self, event: WorkflowEvent) -> None:
        self.events.append(event)
        while len(self.events) > self.maximum_events:
            self.events.popleft()


@dataclass(frozen=True)
class EventRecordingExtension:
    store: EventStore

    def register(self, registry: HarnessRegistry) -> None:
        registry.subscribe(self.store.append)
