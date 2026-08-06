from dataclasses import dataclass

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.memory import (
    EventSchema,
    TaskSchema,
    WorldStateSchema,
)


@dataclass(frozen=True)
class SubAgentContext:
    goal: str
    hypothesis: HypothesisSchema
    current_task: ExecuteActionGroupSchema
    workflow_position: int
    completed_tasks: tuple[TaskSchema, ...]
    world_states: tuple[WorldStateSchema, ...]
    relevant_events: tuple[EventSchema, ...]
