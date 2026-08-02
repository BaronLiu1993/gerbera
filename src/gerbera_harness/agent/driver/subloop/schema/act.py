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
    call_type: ToolCallTypeEnum
    result: object | None = None
    error_message: str | None = None
