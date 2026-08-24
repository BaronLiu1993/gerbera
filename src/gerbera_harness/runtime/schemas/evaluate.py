from typing import Literal

from gerbera_harness.runtime.session import LoopStateEnum, EvaluationDecisionEnum
from gerbera_harness.runtime.schemas.base import HarnessSchema


class AcceptedEvaluationResponseSchema(HarnessSchema):
    decision: Literal[EvaluationDecisionEnum.ACCEPTED]
    next_state: None
    feedback: list[str]


class RejectedEvaluationResponseSchema(HarnessSchema):
    decision: Literal[EvaluationDecisionEnum.REJECTED]
    next_state: None
    feedback: list[str]


class ReplanEvaluationResponseSchema(HarnessSchema):
    decision: Literal[EvaluationDecisionEnum.REPLAN]
    next_state: Literal[LoopStateEnum.TASK_DECOMPOSITION]
    feedback: list[str]


EvaluationDecisionResponseSchema = (
    AcceptedEvaluationResponseSchema
    | RejectedEvaluationResponseSchema
    | ReplanEvaluationResponseSchema
)


class EvaluationResponseSchema(HarnessSchema):
    response: EvaluationDecisionResponseSchema
