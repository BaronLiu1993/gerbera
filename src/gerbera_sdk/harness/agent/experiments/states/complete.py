from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Complete(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.COMPLETE
    system_prompt: ClassVar[str] = "COMPLETE.md"
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.COMPLETE}
    )
