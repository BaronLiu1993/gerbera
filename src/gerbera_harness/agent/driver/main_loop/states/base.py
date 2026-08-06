from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class LoopStateEnum(str, Enum):
    INITIALISATION = "initialisation"
    EXECUTION = "execution"
    REVIEW = "review"


class ReviewDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REPLAN = "replan"


class InitialisationDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CLARIFY = "clarify"


class ExecuteDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ExperimentState:
    state: ClassVar[LoopStateEnum]
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]

    def valid_transition(self, new_state: LoopStateEnum) -> bool:
        return new_state in self.valid_transition_states
