from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class ExecuteLoopStateEnum(str, Enum):
    OBSERVE = "observe"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    DECIDE = "decide"
    ACT = "act"


@dataclass(frozen=True)
class ExecuteLoopState:
    state: ClassVar[ExecuteLoopStateEnum]
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]]

    def valid_transition(self, new_state: ExecuteLoopStateEnum) -> bool:
        return new_state in self.valid_transition_states
