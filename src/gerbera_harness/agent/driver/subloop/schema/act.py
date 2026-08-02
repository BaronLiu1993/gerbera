from enum import Enum

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


class ToolCallStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ToolCallTypeEnum(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


class ToolCallEventSchema(StrictSchema):
    tool_name: str
    status: ToolCallStatusEnum
    result: object | None = None
    call_type: ToolCallTypeEnum
    error_message: str | None = None
