from enum import Enum

from gerbera_harness.runtime.schemas.base import HarnessSchema


class ExecutionDecisionEnum(str, Enum):
    SUCCEEDED = "succeeded"
    CONTINUE = "continue"
    FAILED = "failed"


class ExecutionResultSchema(HarnessSchema):
    decision: ExecutionDecisionEnum
    message: str
