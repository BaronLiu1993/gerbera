from typing import Literal

from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
    ReviewDecisionEnum,
)


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
