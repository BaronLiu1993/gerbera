from enum import Enum
from typing import TypeAlias

from pydantic import TypeAdapter

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


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
