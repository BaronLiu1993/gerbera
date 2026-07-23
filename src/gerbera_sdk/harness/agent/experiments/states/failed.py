from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


# Terminal State
@dataclass(frozen=True)
class Failed(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.FAILED
    prompt_file: ClassVar[str] = "FAILED.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
