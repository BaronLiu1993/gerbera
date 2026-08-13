import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from gerbera_harness.domain.experiment import ExecutionTypeEnum, HypothesisSchema
from gerbera_harness.domain.schema import StrictSchema
from gerbera_harness.domain.session import (
    ExecuteDecisionEnum,
    InitialisationDecisionEnum,
    LoopStateEnum,
    ReviewDecisionEnum,
)


class QuestionSchema(StrictSchema):
    question: str
    options: list[str]


@dataclass
class Question:
    question: str
    options: list[str]
    question_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Answer:
    question_id: str
    question: str
    answer: str


class AcceptedInitialisationResponseSchema(StrictSchema):
    decision: Literal[InitialisationDecisionEnum.ACCEPTED]
    next_state: Literal[LoopStateEnum.EXECUTION]
    hypothesis: HypothesisSchema
    issues: list[str] = Field(max_length=0)
    rejection_reasons: list[str] = Field(max_length=0)
    clarifying_questions: list[QuestionSchema] = Field(max_length=0)


class RejectedInitialisationResponseSchema(StrictSchema):
    decision: Literal[InitialisationDecisionEnum.REJECTED]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    hypothesis: None
    issues: list[str]
    rejection_reasons: list[str] = Field(min_length=1)
    clarifying_questions: list[QuestionSchema] = Field(max_length=0)


class ClarifyInitialisationResponseSchema(StrictSchema):
    decision: Literal[InitialisationDecisionEnum.CLARIFY]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    hypothesis: None
    issues: list[str]
    rejection_reasons: list[str] = Field(max_length=0)
    clarifying_questions: list[QuestionSchema] = Field(min_length=1)


InitialisationDecisionResponseSchema = (
    AcceptedInitialisationResponseSchema
    | RejectedInitialisationResponseSchema
    | ClarifyInitialisationResponseSchema
)


class InitialisationResponseSchema(StrictSchema):
    response: InitialisationDecisionResponseSchema


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


class ExecutionEventSchema(StrictSchema):
    event_name: str
    event_description: str
    event_type: ExecutionTypeEnum
    status: ExecuteDecisionEnum
    position: int = Field(ge=0)
    error_msg: str | None


class ExecuteErrorSchema(StrictSchema):
    event_name: str
    event_type: ExecutionTypeEnum
    position: int = Field(ge=0)
    error: str
