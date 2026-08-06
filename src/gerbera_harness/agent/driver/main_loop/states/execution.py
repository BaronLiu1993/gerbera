from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTION, LoopStateEnum.REVIEW}
    )
