from enum import Enum
from typing import Any, Literal

from pydantic import Field, TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


class ObservationDecision(str, Enum):
    SUCCEEDED = "succeeded"
    RETRY = "retry"
    FAIL = "fail"


class ObservationResult(HarnessSchema):
    actions: list[list[ActionExecuteSchema]] = Field(
        min_length=1,
        max_length=10,
    )


observation_result_adapter = TypeAdapter(ObservationResult)


class ObservationReviewResult(HarnessSchema):
    decision: Literal[
        ObservationDecision.SUCCEEDED,
        ObservationDecision.RETRY,
        ObservationDecision.FAIL,
    ]
    context: str # context for the next iteration


observation_review_result_adapter = TypeAdapter(ObservationReviewResult)


class ObservationIterationRole(str, Enum):
    TOOL = "tool"
    REVIEW = "review"
    OBSERVATION_PLAN = "observation_plan"


class ObservationIterationContext(HarnessSchema):
    iteration: int
    role: Literal[
        ObservationIterationRole.TOOL,
        ObservationIterationRole.REVIEW,
        ObservationIterationRole.OBSERVATION_PLAN,
    ]
    content: dict[str, Any]


observation_iteration_context_adapter = TypeAdapter(
    ObservationIterationContext
)
