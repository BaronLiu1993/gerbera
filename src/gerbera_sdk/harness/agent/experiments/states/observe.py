from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Observe(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.OBSERVE
    system_prompt: ClassVar[str] = "OBSERVE.md"
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.REVIEW}
    )
