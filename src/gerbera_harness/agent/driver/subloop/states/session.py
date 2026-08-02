from dataclasses import dataclass, field

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.act import ActState
from gerbera_harness.agent.driver.subloop.states.observe import (
    ObserveState,
)
from gerbera_harness.agent.driver.subloop.states.plan import PlanState


STATE_TYPES: dict[ExecuteLoopStateEnum, type[ExecuteLoopState]] = {
    ExecuteLoopStateEnum.OBSERVE: ObserveState,
    ExecuteLoopStateEnum.PLAN: PlanState,
    ExecuteLoopStateEnum.ACT: ActState,
}


@dataclass
class Session:
    state: ExecuteLoopState = field(default_factory=ObserveState)

    def perform_transition(
        self,
        target_state: ExecuteLoopStateEnum,
    ) -> ExecuteLoopState:
        if not self.valid_transition(target_state):
            raise ValueError("Invalid transition state")

        self.state = STATE_TYPES[target_state]()
        return self.state

    def valid_transition(
        self,
        new_state: ExecuteLoopStateEnum,
    ) -> bool:
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)
