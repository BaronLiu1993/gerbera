from enum import Enum

from pydantic import TypeAdapter
from typing_extensions import TypeAlias

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)

PlanningExecuteActionSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)


class PlanningStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"
    COMPLETE = "complete"


class PlanningResponseSchema(HarnessSchema):
    action: PlanningExecuteActionSchema


class PlanningReviewSchema(HarnessSchema):
    status: PlanningStatusEnum
    feedback: str


planning_adapter = TypeAdapter(PlanningResponseSchema)
planning_review_adapter = TypeAdapter(PlanningReviewSchema)
