from enum import Enum

from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class ExecutionStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ExecutionTypeEnum(str, Enum):
    RULE = "rule"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    AGENT = "agent"


class ExecutionEventSchema(StrictSchema):
    event_name: str
    event_description: str
    event_type: ExecutionTypeEnum
    status: ExecutionStatusEnum
    position: int  # Position in the linear steps.
    error_msg: str
