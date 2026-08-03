import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import JsonValue

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.memory.event_schema import (
    EventSchema,
    EventTypeEnum,
    SourceTypeEnum,
)
from gerbera_harness.memory.task_schema import TaskSchema
from gerbera_harness.memory.world_state_schema import WorldStateSchema


@dataclass
class Memory:
    goal: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[dict[str, object]] = field(default_factory=list)
    current_hypothesis: HypothesisSchema | None = None
    remaining_tasks: list[TaskSchema] = field(default_factory=list)
    completed_tasks: list[TaskSchema] = field(default_factory=list)
    event_ledger: list[EventSchema] = field(default_factory=list)
    world_state_ledger: list[WorldStateSchema] = field(
        default_factory=list
    )

    def append_message(self, role: str, content: object) -> None:
        self.messages.append({"role": role, "content": content})

    def append_event(
        self,
        *,
        event_type: EventTypeEnum,
        source_type: SourceTypeEnum,
        payload: dict[str, Any],
    ) -> EventSchema:
        event = EventSchema(
            event_type=event_type,
            source_type=source_type,
            payload=payload,
            session_id=self.session_id,
        )
        self.event_ledger.append(event)
        return event

    def append_world_state(
        self,
        state: dict[str, JsonValue],
    ) -> WorldStateSchema:
        world_state = WorldStateSchema(
            observed_at=datetime.now(timezone.utc),
            state=state,
        )
        self.world_state_ledger.append(world_state)
        return world_state

    def set_hypothesis(self, hypothesis: HypothesisSchema) -> None:
        self.current_hypothesis = hypothesis
