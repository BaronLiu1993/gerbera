from pydantic import Field

from gerbera_harness.runtime.schemas.execute import ExecutionTypeEnum
from gerbera_harness.runtime.session import ExecuteDecisionEnum
from gerbera_harness.runtime.utils import StrictSchema


class ExecutionEventSchema(StrictSchema):
    event_name: str
    event_description: str
    event_type: ExecutionTypeEnum
    status: ExecuteDecisionEnum
    position: int = Field(ge=0)
    error_msg: str | None = None


class ExecuteErrorSchema(StrictSchema):
    event_name: str
    event_type: ExecutionTypeEnum
    position: int = Field(ge=0)
    error: str
