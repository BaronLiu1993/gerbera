from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.experiment import ExecuteActionGroupSchema
from gerbera_harness.runtime.execute_producer.schemas.states import LoopDecision


class ObservationAction(HarnessSchema):
    summary: str
    action_groups: list[ExecuteActionGroupSchema]


class ObservationResult(HarnessSchema):
    summary: str
    result: LoopDecision
