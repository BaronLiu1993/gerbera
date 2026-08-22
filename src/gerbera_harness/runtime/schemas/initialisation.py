import uuid
from typing import Literal

from pydantic import Field

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.runtime.schemas.base import HarnessSchema


# Clarification exchange.

class Question(HarnessSchema):
    question: str
    options: list[str]
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Answer(HarnessSchema):
    question_id: str
    question: str
    answer: str

class InitialisationTaskMetadataSchema(HarnessSchema):
    task_goal: str
    success_criteria: list[str] = Field(min_length=1)


class InitialisationIntentSchema(HarnessSchema):
    goal: str
    context_summary: str
    tasks: list[InitialisationTaskMetadataSchema] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(min_length=1)
    # this sucess criteria is for the whole thing

class AcceptedInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.ACCEPTED]
    next_state: Literal[LoopStateEnum.EXECUTION]

class RejectedInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.REJECTED]
    next_state: Literal[LoopStateEnum.INITIALISATION]

class ClarifyInitialisationResponseSchema(HarnessSchema):
    decision: Literal[InitialisationDecisionEnum.CLARIFY]
    next_state: Literal[LoopStateEnum.INITIALISATION]
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
    intent: InitialisationIntentSchema
