from typing import Literal

from gerbera_harness.runtime.state_machine import LoopStateEnum, ReviewDecisionEnum
from gerbera_harness.runtime.schemas.base import HarnessSchema


class AcceptedReviewResponseSchema(HarnessSchema):
    decision: Literal[ReviewDecisionEnum.ACCEPTED]
    next_state: None
    feedback: list[str]


class RejectedReviewResponseSchema(HarnessSchema):
    decision: Literal[ReviewDecisionEnum.REJECTED]
    next_state: None
    feedback: list[str]


class ReplanReviewResponseSchema(HarnessSchema):
    decision: Literal[ReviewDecisionEnum.REPLAN]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    feedback: list[str]


ReviewDecisionResponseSchema = (
    AcceptedReviewResponseSchema
    | RejectedReviewResponseSchema
    | ReplanReviewResponseSchema
)


class ReviewResponseSchema(HarnessSchema):
    response: ReviewDecisionResponseSchema
