from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Hypothesize(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.HYPOTHESIZE
    system_prompt: ClassVar[str] = "HYPOTHESIZE.md"
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.PLAN}
    )
