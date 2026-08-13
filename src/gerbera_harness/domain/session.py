from __future__ import annotations

import uuid
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Initialisation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.INITIALISATION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.INITIALISATION, LoopStateEnum.EXECUTION}
    )


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTION, LoopStateEnum.REVIEW}
    )


@dataclass(frozen=True)
class Review(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.INITIALISATION}
    )


STATE_TYPES: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.INITIALISATION: Initialisation,
    LoopStateEnum.EXECUTION: Execution,
    LoopStateEnum.REVIEW: Review,
}


@dataclass
class Session:
    state: ExperimentState = field(default_factory=Initialisation)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def valid_transition(self, new_state: LoopStateEnum | str) -> bool:
        target_state = LoopStateEnum(new_state)
        return self.state.valid_transition(target_state)

    def perform_transition(
        self,
        new_state: LoopStateEnum | str,
    ) -> ExperimentState:
        target_state = LoopStateEnum(new_state)
        if not self.state.valid_transition(target_state):
            raise ValueError(
                f"Invalid transition: {self.state.state.value} "
                f"-> {target_state.value}"
            )
        self.state = STATE_TYPES[target_state]()
        return self.state
