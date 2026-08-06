from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)
from gerbera_harness.memory import WorldStateSchema


@dataclass(frozen=True)
class SubAgentResult:
    decision: ExecuteDecisionEnum
    errors: list[ExecuteErrorSchema]
    turns_completed: int
    observations: list[WorldStateSchema] = field(default_factory=list)
    tool_events: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (
            self.decision is ExecuteDecisionEnum.ACCEPTED
            and self.errors
        ):
            raise ValueError("Accepted subagent results cannot contain errors")
