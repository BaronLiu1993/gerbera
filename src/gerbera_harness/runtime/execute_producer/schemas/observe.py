from enum import Enum

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


# Keep observe/planning/review decisions separate even when values overlap.
# Each state can grow domain-specific outcomes without changing the others.
class ObservationDecision(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"


class ObservationAction(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]

class ObservationResult(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]
    result: ObservationDecision
