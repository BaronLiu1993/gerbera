from enum import Enum

from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class ExecutionTypeEnum(str, Enum):
    RULE = "rule"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    AGENT = "agent"


class ExecutionEventSchema(StrictSchema):
    event_name: str
    event_description: str
    event_type: ExecutionTypeEnum
    status: ExecuteDecisionEnum
    position: int  # Position in the linear steps.
    error_msg: str


class ExecuteErrorSchema(StrictSchema):
    event_name: str
    event_type: ExecutionTypeEnum
    position: int
    error: str
