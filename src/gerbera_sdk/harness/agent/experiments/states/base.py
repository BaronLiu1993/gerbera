from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class LoopStateEnum(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass(frozen=True)
class ExperimentState:
    phase: ClassVar[LoopStateEnum]
    valid_states: ClassVar[frozenset[LoopStateEnum]]

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return state in self.valid_states
