from typing import Literal

from gerbera_harness.runtime.session import LoopStateEnum, ReviewDecisionEnum
from gerbera_harness.runtime.utils import StrictSchema


class AcceptedReviewResponseSchema(StrictSchema):
    decision: Literal[ReviewDecisionEnum.ACCEPTED]
    next_state: None
    feedback: list[str]


class RejectedReviewResponseSchema(StrictSchema):
    decision: Literal[ReviewDecisionEnum.REJECTED]
    next_state: None
    feedback: list[str]


class ReplanReviewResponseSchema(StrictSchema):
    decision: Literal[ReviewDecisionEnum.REPLAN]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    feedback: list[str]


ReviewDecisionResponseSchema = (
    AcceptedReviewResponseSchema
    | RejectedReviewResponseSchema
    | ReplanReviewResponseSchema
)


class ReviewResponseSchema(StrictSchema):
    response: ReviewDecisionResponseSchema
