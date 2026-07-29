from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class ActState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.ACT
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset({ExecuteLoopStateEnum.OBSERVE})
