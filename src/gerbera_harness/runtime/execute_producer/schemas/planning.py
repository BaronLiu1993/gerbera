from enum import Enum
from typing import Literal

from pydantic import Field
from pydantic import TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


# Keep observe/planning/review decisions separate even when values overlap.
# Each state can grow domain-specific outcomes without changing the others.
class PlanningDecision(str, Enum):
    SUCCEEDED = "succeeded"
    ALREADY_COMPLETED = "already_completed"
    FAIL = "fail"


class SucceededPlanningResult(HarnessSchema):
    decision: Literal[PlanningDecision.SUCCEEDED]
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(min_length=1)


class AlreadyCompletedPlanningResult(HarnessSchema):
    decision: Literal[PlanningDecision.ALREADY_COMPLETED]
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(max_length=0)


class FailedPlanningResult(HarnessSchema):
    decision: Literal[PlanningDecision.FAIL]
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(max_length=0)


PlanningResult = (
    SucceededPlanningResult
    | AlreadyCompletedPlanningResult
    | FailedPlanningResult
)
planning_result_adapter = TypeAdapter(PlanningResult)
