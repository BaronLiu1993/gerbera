import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.runtime.utils import StrictSchema
from gerbera_harness.runtime.schemas.experiment import HypothesisSchema


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
