from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class IncompleteState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.INCOMPLETE
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset({ExecuteLoopStateEnum.DECIDE})
