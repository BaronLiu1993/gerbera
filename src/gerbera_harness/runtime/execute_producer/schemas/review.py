from enum import Enum

from gerbera_harness.runtime.schemas.base import HarnessSchema


# Keep observe/planning/review decisions separate even when values overlap.
# Each state can grow domain-specific outcomes without changing the others.
class ExecuteProducerDecision(str, Enum):
    SUCCESS = "success"
    REPLAN_ACTIONS = "replan_actions"
    REDECOMPOSE_TASKS = "redecompose_tasks"
    FAIL = "fail"


class ExecuteProducerResult(HarnessSchema):
    decision: ExecuteProducerDecision
    context: str
