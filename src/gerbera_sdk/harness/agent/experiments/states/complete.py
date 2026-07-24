from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


# Terminal State, we have proved the hypothesis
@dataclass(frozen=True)
class Complete(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.COMPLETE
    prompt_file: ClassVar[str] = "COMPLETE.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
