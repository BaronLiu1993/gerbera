from dataclasses import dataclass, field

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)

from gerbera_harness.agent.driver.subloop.states.observe import (
    ObserveState,
)


@dataclass
class Session:
    state: ExecuteLoopState = field(default_factory=ObserveState)

    def perform_transition(self, target_state: ExecuteLoopStateEnum) -> ExecuteLoopStateEnum:
        if not self.valid_transition(target_state):
            raise ValueError(f"Invalid Transition State")
        return target_state

    def valid_transition(
        self,
        new_state: ExecuteLoopStateEnum,
    ) -> bool:
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)