from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class PlanState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.PLAN
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset(
        {
            ExecuteLoopStateEnum.ACT,
            ExecuteLoopStateEnum.OBSERVE,
        }
    )
