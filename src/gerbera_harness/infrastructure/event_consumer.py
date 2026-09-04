from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)
from gerbera_harness.runtime.schemas.base import HarnessSchema


class RuntimeEventEnvelope(HarnessSchema):
    session_id: str
    payload: dict[str, Any]


@dataclass
class EventConsumer:
    memory_bus: dict[str, Memory] = field(default_factory=dict)

    def register_memory(self, memory: Memory) -> None:
        self.memory_bus[memory.session_id] = memory

    # def ingest_runtime_event(
    #     self,
    #     envelope: RuntimeEventEnvelope | dict[str, Any],
    # ) -> EventSchema:
    #     runtime_event = RuntimeEventEnvelope.model_validate(envelope)
    #     memory = self.memory_bus.get(runtime_event.session_id)

    #     task_id = memory.require_task_state().current_task_id
    #     event = EventSchema(
    #         session_id=runtime_event.session_id,
    #         event_type=EventTypeEnum.RUNTIME_EVENT,
    #         source_type=SourceTypeEnum.RUNTIME,
    #         source_name="runtime_event_consumer",
    #         payload=runtime_event.payload,
    #         task_id=task_id,
    #     )
    #     memory.insert_event(event)