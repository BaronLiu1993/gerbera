import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class LoopStateEnum(str, Enum):
    TASK_DECOMPOSITION = "task_decomposition"
    EXECUTION = "execution"
    EVALUATION = "evaluation"


class EvaluationDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REPLAN = "replan"


class TaskDecompositionDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CLARIFY = "clarify"


class ExecuteDecisionEnum(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExperimentState:
    state: ClassVar[LoopStateEnum]
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]

    def valid_transition(self, new_state: LoopStateEnum) -> bool:
        return new_state in self.valid_transition_states


@dataclass(frozen=True)
class TaskDecomposition(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.TASK_DECOMPOSITION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.TASK_DECOMPOSITION, LoopStateEnum.EXECUTION}
    )


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {
            LoopStateEnum.TASK_DECOMPOSITION,
            LoopStateEnum.EXECUTION,
            LoopStateEnum.EVALUATION,
        }
    )


@dataclass(frozen=True)
class Evaluation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EVALUATION
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.TASK_DECOMPOSITION}
    )


STATE_TYPES: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.TASK_DECOMPOSITION: TaskDecomposition,
    LoopStateEnum.EXECUTION: Execution,
    LoopStateEnum.EVALUATION: Evaluation,
}


@dataclass
class Session:
    state: ExperimentState = field(default_factory=TaskDecomposition)
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
