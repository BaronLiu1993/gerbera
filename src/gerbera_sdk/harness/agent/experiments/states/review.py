from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)



@dataclass(frozen=True)
class Review(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    system_prompt: ClassVar[str] = "REVIEW.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {
            LoopStateEnum.EXECUTION,
            LoopStateEnum.COMPLETE,
            LoopStateEnum.FAILED,
        }
    )
    valid_schema: ClassVar[dict] = build_valid_schema(valid_transition_states)
