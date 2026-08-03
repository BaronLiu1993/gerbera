from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.event_schema import (
    EventSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    TaskSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.world_state_schema import (
    WorldStateSchema,
)


@dataclass
class Memory:
    messages: list[dict[str, object]] = field(default_factory=list)
    current_hypothesis: HypothesisSchema | None = None
    remaining_tasks: list[TaskSchema] = field(default_factory=list)
    completed_tasks: list[TaskSchema] = field(default_factory=list)
    event_ledger: list[EventSchema] = field(default_factory=list)
    world_state_ledger: list[WorldStateSchema] = field(
        default_factory=list
    )
