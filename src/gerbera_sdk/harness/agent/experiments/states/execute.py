from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Execute(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTE
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.OBSERVE}
    )
