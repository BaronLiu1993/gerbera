from enum import Enum

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


class ExecuteLoopDecisionEnum(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONTINUE = "continue"


class DecideResultSchema(StrictSchema):
    decision: ExecuteLoopDecisionEnum
