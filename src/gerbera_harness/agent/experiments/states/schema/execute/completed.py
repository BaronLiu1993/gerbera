from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


@dataclass(frozen=True)
class CompletedState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.COMPLETED
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset()
