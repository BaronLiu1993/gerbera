from enum import Enum

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema


class ToolCallStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ToolCallTypeEnum(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


class ToolCallEventSchema(HarnessSchema):
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    status: ToolCallStatusEnum
    call_type: ToolCallTypeEnum
    result: object | None = None
    error_message: str | None = None
