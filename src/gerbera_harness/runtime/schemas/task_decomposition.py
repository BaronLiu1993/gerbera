import uuid
from typing import Literal

from pydantic import Field

from gerbera_harness.runtime.session import (
    TaskDecompositionDecisionEnum,
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

class TaskDecompositionTaskMetadataSchema(HarnessSchema):
    task_goal: str
    success_criteria: list[str] = Field(min_length=1)


class TaskDecompositionIntentSchema(HarnessSchema):
    goal: str
    context_summary: str
    tasks: list[TaskDecompositionTaskMetadataSchema] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(min_length=1)
    # this sucess criteria is for the whole thing

class AcceptedTaskDecompositionResponseSchema(HarnessSchema):
    decision: Literal[TaskDecompositionDecisionEnum.ACCEPTED]
    next_state: Literal[LoopStateEnum.EXECUTION]

class RejectedTaskDecompositionResponseSchema(HarnessSchema):
    decision: Literal[TaskDecompositionDecisionEnum.REJECTED]
    next_state: Literal[LoopStateEnum.TASK_DECOMPOSITION]

class ClarifyTaskDecompositionResponseSchema(HarnessSchema):
    decision: Literal[TaskDecompositionDecisionEnum.CLARIFY]
    next_state: Literal[LoopStateEnum.TASK_DECOMPOSITION]
    clarifying_questions: list[Question] = Field(min_length=1)


TaskDecompositionDecisionResponseSchema = (
    AcceptedTaskDecompositionResponseSchema
    | RejectedTaskDecompositionResponseSchema
    | ClarifyTaskDecompositionResponseSchema
)

class TaskDecompositionResponseSchema(HarnessSchema):
    response: TaskDecompositionDecisionResponseSchema


class TaskDecompositionResultSchema(HarnessSchema):
    decision: TaskDecompositionDecisionEnum
    intent: TaskDecompositionIntentSchema
