from enum import Enum

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


# Keep observe/planning/review decisions separate even when values overlap.
# Each state can grow domain-specific outcomes without changing the others.
class PlanningDecision(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"


class PlanningAction(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(min_length=1)


class PlanningResult(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]
    result: PlanningDecision
