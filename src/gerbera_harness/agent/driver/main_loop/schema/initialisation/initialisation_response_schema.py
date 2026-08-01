from pydantic import model_validator

from gerbera_harness.agent.driver.main_loop.schema.hypothesis import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.initialisation.clarification_schema import (
    QuestionSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from gerbera_harness.agent.driver.main_loop.states.base import (
    InitialistationDecisionEnum as InitialisationDecisionEnum,
    LoopStateEnum,
)


class InitialisationResponseSchema(StrictSchema):
    decision: InitialisationDecisionEnum
    next_state: LoopStateEnum
    issues: list[str]
    clarifying_questions: list[QuestionSchema]

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "InitialisationResponseSchema":
        if self.decision is InitialisationDecisionEnum.ACCEPTED:
            if self.hypothesis is None:
                raise ValueError("ACCEPTED requires a hypothesis")
            if self.clarifying_questions:
                raise ValueError(
                    "ACCEPTED cannot contain clarifying questions"
                )

        elif self.decision is InitialisationDecisionEnum.CLARIFY:
            if not self.clarifying_questions:
                raise ValueError(
                    "CLARIFY requires at least one question"
                )
            if self.next_state is not LoopStateEnum.INITIALISATION:
                raise ValueError(
                    "CLARIFY must remain in INITIALISATION"
                )

        elif self.decision is InitialisationDecisionEnum.REJECTED:
            if self.hypothesis is not None:
                raise ValueError(
                    "REJECTED cannot contain a hypothesis"
                )
            if self.clarifying_questions:
                raise ValueError(
                    "REJECTED cannot contain clarifying questions"
                )

        return self
