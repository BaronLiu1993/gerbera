from dataclasses import dataclass

from gerbera_harness.memory.schemas.events import EventSchema
from gerbera_harness.memory.schemas.task import TaskSchema
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.runtime.schemas.experiment import (
    ExecuteActionGroupSchema,
    HypothesisSchema,
)


@dataclass(frozen=True)
class SubAgentContext:
    session_id: str
    goal: str
    hypothesis: HypothesisSchema
    current_task: ExecuteActionGroupSchema
    workflow_position: int
    completed_tasks: tuple[TaskSchema, ...]
    world_states: tuple[WorldStateSchema, ...]
    relevant_events: tuple[EventSchema, ...]
