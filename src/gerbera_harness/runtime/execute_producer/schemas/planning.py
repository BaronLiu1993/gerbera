from enum import Enum
from typing import Any, Literal

from pydantic import Field
from pydantic import TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


class PlanningResult(HarnessSchema):
    plan: str
    actions: list[list[ActionExecuteSchema]] = Field(
        default_factory=list,
        max_length=10,
    )


planning_result_adapter = TypeAdapter(PlanningResult)


class PlanningReviewDecision(str, Enum):
    APPROVED = "approved"
    REVISE = "revise"
    FAIL = "fail"


class PlanningReviewResult(HarnessSchema):
    decision: Literal[
        PlanningReviewDecision.APPROVED,
        PlanningReviewDecision.REVISE,
        PlanningReviewDecision.FAIL,
    ]
    context: str


planning_review_result_adapter = TypeAdapter(PlanningReviewResult)


class PlanningIterationRole(str, Enum):
    PLAN = "plan"
    TOOL = "tool"
    REVIEW = "review"


class PlanningIterationContext(HarnessSchema):
    iteration: int
    role: Literal[
        PlanningIterationRole.PLAN,
        PlanningIterationRole.TOOL,
        PlanningIterationRole.REVIEW,
    ]
    content: dict[str, Any]


planning_iteration_context_adapter = TypeAdapter(PlanningIterationContext)
