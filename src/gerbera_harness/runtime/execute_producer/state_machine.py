from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

class ExecuteLoopStateEnum(str, Enum):
    OBSERVE = "observe"
    PLAN = "plan"
    REVIEW = "review"

# Base Class
@dataclass(frozen=True)
class ExecuteLoopState:
    state: ClassVar[ExecuteLoopStateEnum]
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]]

    def valid_transition(self, new_state: ExecuteLoopStateEnum) -> bool:
        return new_state in self.valid_transition_states


@dataclass(frozen=True)
class ObserveState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.OBSERVE
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.PLAN})
    )


@dataclass(frozen=True)
class PlanState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.PLAN
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.REVIEW, ExecuteLoopStateEnum.OBSERVE})
    )

@dataclass(frozen=True)
class ReviewState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.REVIEW
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.OBSERVE, ExecuteLoopStateEnum.PLAN})
    )


EXECUTE_PRODUCER_STATE_TYPES: dict[ExecuteLoopStateEnum, type[ExecuteLoopState]] = {
    ExecuteLoopStateEnum.OBSERVE: ObserveState,
    ExecuteLoopStateEnum.PLAN: PlanState,
    ExecuteLoopStateEnum.REVIEW: ReviewState,
}

@dataclass
class StateMachine:
    state: ExecuteLoopState = field(default_factory=ObserveState)

    @property
    def current_state(self) -> ExecuteLoopStateEnum:
        return self.state.state

    def perform_transition(
        self,
        target_state: ExecuteLoopStateEnum,
    ) -> ExecuteLoopState:
        if not self.valid_transition(target_state):
            raise ValueError("Invalid transition state")
        
        self.state = EXECUTE_PRODUCER_STATE_TYPES[target_state]()
        return self.state

    def valid_transition(self, new_state: ExecuteLoopStateEnum) -> bool:
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)
