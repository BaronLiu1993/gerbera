from enum import Enum

from pydantic import TypeAdapter
from typing_extensions import TypeAlias

from gerbera_harness.runtime.utils import StrictSchema
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


class PlanningResponseSchema(StrictSchema):
    action: PlanningExecuteActionSchema


class PlanningReviewSchema(StrictSchema):
    status: PlanningStatusEnum
    feedback: str


planning_adapter = TypeAdapter(PlanningResponseSchema)
planning_review_adapter = TypeAdapter(PlanningReviewSchema)
