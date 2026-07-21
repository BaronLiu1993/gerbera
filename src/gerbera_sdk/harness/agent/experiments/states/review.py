from dataclasses import dataclass
from typing import ClassVar
from enum import Enum

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)

class ReviewDecision(Enum):
    RETRY_EXPERIMENT = "retry_experiment"
    NEW_HYPOTHESIS = "new_hypothesis"
    COMPLETE = "complete"

REVIEW_TRANSITIONS = {
    ReviewDecision.RETRY_EXPERIMENT: LoopStateEnum.PLAN,
    ReviewDecision.NEW_HYPOTHESIS: LoopStateEnum.HYPOTHESIZE,
    ReviewDecision.COMPLETE: LoopStateEnum.COMPLETE,
}

@dataclass(frozen=True)
class Review(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    system_prompt: ClassVar[str] = "REVIEW.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {
            LoopStateEnum.HYPOTHESIZE,
            LoopStateEnum.PLAN,
            LoopStateEnum.COMPLETE,
        }
    )
    valid_schema: ClassVar[dict] = build_valid_schema(valid_transition_states)
