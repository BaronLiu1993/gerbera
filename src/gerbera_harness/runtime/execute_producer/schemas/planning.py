from pydantic import Field

from gerbera_harness.runtime.execute_producer.session import LoopDecision
from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


class PlanningAction(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]] = Field(min_length=1)


class PlanningResult(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]
    result: LoopDecision
