from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


# Two decisions here, either we give up and execute or if we observed something we can go and generate a new hypothesis and try again
@dataclass(frozen=True)
class Failed(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.FAILED
    prompt_file: ClassVar[str] = "FAILED.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
