from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Initialisation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.INITIALISATION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.INITIALISATION, LoopStateEnum.EXECUTION}
    )
