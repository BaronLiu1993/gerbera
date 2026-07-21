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
    system_prompt: ClassVar[str] = "FAILED.md"
