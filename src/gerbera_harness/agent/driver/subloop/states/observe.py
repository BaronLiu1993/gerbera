from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class ObserveState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.OBSERVE
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset({ExecuteLoopStateEnum.DECIDE})
