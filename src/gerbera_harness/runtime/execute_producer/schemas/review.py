from gerbera_harness.runtime.execute_producer.session import LoopDecision
from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


class ReviewAction(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]

class ReviewResult(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]
    result: LoopDecision
