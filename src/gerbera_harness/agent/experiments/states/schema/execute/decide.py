from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class DecideState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.DECIDE
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset({ExecuteLoopStateEnum.ACT})
