from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    TextResponseSchema,
    build_valid_schema,
)



@dataclass(frozen=True)
class Review(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    prompt_file: ClassVar[str] = "REVIEW.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {
            LoopStateEnum.EXECUTION,
            LoopStateEnum.COMPLETE,
            LoopStateEnum.FAILED,
        }
    )
    valid_schema: ClassVar[dict] = build_valid_schema(
        valid_transition_states,
        TextResponseSchema,
    )
