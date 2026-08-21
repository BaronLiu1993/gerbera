import uuid
from typing import Literal

from pydantic import Field

from gerbera_harness.runtime.state_machine import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.runtime.schemas.base import HarnessSchema


class Question(HarnessSchema):
    question: str
    options: list[str]
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Answer(HarnessSchema):
    question_id: str
    question: str
    answer: str


class InitialisationIntentSchema(HarnessSchema):
    user_intent: str
    goal: str
    context_summary: str
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)


class AcceptedInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.ACCEPTED]
    next_state: Literal[LoopStateEnum.EXECUTION]
    issues: list[str] = Field(max_length=0)
    rejection_reasons: list[str] = Field(max_length=0)
    clarifying_questions: list[Question] = Field(max_length=0)


class RejectedInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.REJECTED]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    issues: list[str]
    rejection_reasons: list[str] = Field(min_length=1)
    clarifying_questions: list[Question] = Field(max_length=0)


class ClarifyInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.CLARIFY]
    next_state: Literal[LoopStateEnum.INITIALISATION]
    issues: list[str]
    rejection_reasons: list[str] = Field(max_length=0)
    clarifying_questions: list[Question] = Field(min_length=1)


InitialisationDecisionResponseSchema = (
    AcceptedInitialisationResponseSchema
    | RejectedInitialisationResponseSchema
    | ClarifyInitialisationResponseSchema
)


class InitialisationResponseSchema(HarnessSchema):
    response: InitialisationDecisionResponseSchema


class InitialisationResultSchema(HarnessSchema):
    decision: InitialisationDecisionEnum
    requested_next_state: LoopStateEnum
    intent: InitialisationIntentSchema
    clarifying_questions: list[Question] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
