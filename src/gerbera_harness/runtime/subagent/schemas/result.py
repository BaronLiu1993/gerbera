from pydantic import Field

from gerbera_harness.runtime.schemas.execution import ExecuteErrorSchema
from gerbera_harness.runtime.session import ExecuteDecisionEnum
from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.memory.schemas.world import WorldStateSchema


class SubAgentResult(HarnessSchema):
    decision: ExecuteDecisionEnum
    errors: list[ExecuteErrorSchema]
    turns_completed: int
    observations: list[WorldStateSchema] = Field(default_factory=list)
    tool_events: list[dict[str, object]] = Field(default_factory=list)
