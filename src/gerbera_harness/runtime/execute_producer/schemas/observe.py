from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema
from gerbera_harness.runtime.execute_producer.state_machine import LoopDecision

class ObservationAction(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]

class ObservationResult(HarnessSchema):
    context: str
    actions: list[list[ActionExecuteSchema]]
    result: LoopDecision
