from pydantic import Field

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class ExecutionEventSchema(StrictSchema):
    event_name: str
    event_description: str
    event_type: ExecutionTypeEnum
    status: ExecuteDecisionEnum
    position: int = Field(ge=0)  # Position in the linear steps.
    error_msg: str | None


class ExecuteErrorSchema(StrictSchema):
    event_name: str
    event_type: ExecutionTypeEnum
    position: int = Field(ge=0)
    error: str
