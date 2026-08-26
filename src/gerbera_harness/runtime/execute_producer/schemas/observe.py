from enum import Enum
from typing import Literal

from pydantic import Field, TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


# Keep observe/planning/review decisions separate even when values overlap.
# Each state can grow domain-specific outcomes without changing the others.
class ObservationDecision(str, Enum):
    SUCCEEDED = "succeeded"
    FAIL = "fail"


class SucceededObservationResult(HarnessSchema):
    decision: Literal[ObservationDecision.SUCCEEDED]
    context: str
    actions: list[list[ActionExecuteSchema]]


class FailedObservationResult(HarnessSchema):
    decision: Literal[ObservationDecision.FAIL]
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(max_length=0)


ObservationResult = SucceededObservationResult | FailedObservationResult
observation_result_adapter = TypeAdapter(ObservationResult)
