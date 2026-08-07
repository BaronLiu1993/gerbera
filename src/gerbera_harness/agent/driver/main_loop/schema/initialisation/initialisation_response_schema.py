from typing import Literal

from pydantic import Field

from gerbera_harness.agent.driver.main_loop.schema.initialisation.clarification_schema import (
    QuestionSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from gerbera_harness.agent.driver.main_loop.states.base import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)


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
