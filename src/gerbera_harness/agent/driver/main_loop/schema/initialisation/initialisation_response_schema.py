from typing import Literal

from pydantic import model_validator

from gerbera_harness.agent.driver.main_loop.schema.initialisation.clarification_schema import (
    QuestionSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from gerbera_harness.agent.driver.main_loop.states.base import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)


class InitialisationResponseSchema(StrictSchema):
    decision: InitialisationDecisionEnum
    next_state: Literal[
        LoopStateEnum.INITIALISATION,
        LoopStateEnum.EXECUTION,
    ]
    issues: list[str]
    rejection_reasons: list[str]
    clarifying_questions: list[QuestionSchema]

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "InitialisationResponseSchema":
        if self.decision is InitialisationDecisionEnum.ACCEPTED:
            if self.clarifying_questions:
                raise ValueError(
                    "ACCEPTED cannot contain clarifying questions"
                )
            if self.next_state is not LoopStateEnum.EXECUTION:
                raise ValueError("ACCEPTED must transition to EXECUTION")

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
            if self.clarifying_questions:
                raise ValueError(
                    "REJECTED cannot contain clarifying questions"
                )
            if self.next_state is not LoopStateEnum.INITIALISATION:
                raise ValueError(
                    "REJECTED must remain in INITIALISATION"
                )

        return self
