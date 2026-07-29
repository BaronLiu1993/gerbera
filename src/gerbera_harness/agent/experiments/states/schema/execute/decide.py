from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from gerbera_harness.agent.experiments.states.schema.utils import StrictSchema
from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)


class ExecuteLoopDecisionEnum(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONTINUE = "continue"


class DecideResultSchema(StrictSchema):
    decision: ExecuteLoopDecisionEnum


@dataclass(frozen=True)
class DecideState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.DECIDE
    valid_transition_states: ClassVar[
        frozenset[ExecuteLoopStateEnum]
    ] = frozenset()
