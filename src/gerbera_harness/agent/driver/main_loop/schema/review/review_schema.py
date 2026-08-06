from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from gerbera_harness.agent.driver.main_loop.schema.hypothesis import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
    ReviewDecisionEnum,
)


class ReviewResponseSchema(StrictSchema):
    decision: ReviewDecisionEnum
    next_state: Literal[LoopStateEnum.INITIALISATION] | None
    hypothesis: HypothesisSchema | None

    @model_validator(mode="after")
    def validate_decision_transition(self) -> "ReviewResponseSchema":
        if self.decision is ReviewDecisionEnum.ACCEPTED:
            if self.next_state is not None:
                raise ValueError("ACCEPTED review must finish the workflow")
        elif self.next_state is not LoopStateEnum.INITIALISATION:
            raise ValueError(
                "REJECTED review must return to INITIALISATION"
            )
        return self
