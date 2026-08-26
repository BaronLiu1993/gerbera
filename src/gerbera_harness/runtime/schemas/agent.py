from enum import Enum

from gerbera_harness.runtime.schemas.base import HarnessSchema


class AgentStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class AgentResultSchema(HarnessSchema):
    status: AgentStatusEnum
    message: str
