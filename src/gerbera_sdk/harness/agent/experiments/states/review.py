from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Review(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    system_prompt: ClassVar[str] = "REVIEW.md"
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.PLAN}
    )
