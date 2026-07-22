from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


# Terminal State
@dataclass(frozen=True)
class Complete(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.COMPLETE
    system_prompt: ClassVar[str] = "COMPLETE.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
