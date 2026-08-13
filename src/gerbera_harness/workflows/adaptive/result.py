from dataclasses import dataclass, field

from gerbera_harness.domain.session import (
    ExecuteDecisionEnum,
)
from gerbera_harness.domain.responses import (
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
