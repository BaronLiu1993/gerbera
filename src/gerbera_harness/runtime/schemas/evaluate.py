from enum import Enum

from gerbera_harness.runtime.schemas.base import HarnessSchema


class EvaluationDecisionEnum(str, Enum):
    SUCCEEDED = "succeeded"
    CONTINUE = "continue"
    FAILED = "failed"


class EvaluationResultSchema(HarnessSchema):
    decision: EvaluationDecisionEnum
    # Summary of everything that happened in this session.
    context: str
