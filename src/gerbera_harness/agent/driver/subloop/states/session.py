from dataclasses import dataclass, field

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.act import (
    ActState,
)
from gerbera_harness.agent.driver.subloop.schema.decide import (
    ExecuteLoopDecisionEnum,
)
from gerbera_harness.agent.driver.subloop.states.decide import (
    DecideState,
)
from gerbera_harness.agent.driver.subloop.states.observe import (
    ObserveState,
)


@dataclass
class ExecuteLoop:
    state: ExecuteLoopState = field(default_factory=ObserveState)
    decision: ExecuteLoopDecisionEnum | None = None

    @property
    def terminated(self) -> bool:
        return self.decision in {
            ExecuteLoopDecisionEnum.COMPLETE,
            ExecuteLoopDecisionEnum.INCOMPLETE,
        }

    def valid_transition(
        self,
        new_state: ExecuteLoopStateEnum | str,
    ) -> bool:
        if self.terminated:
            return False
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)

    def perform_transition(
        self,
        new_state: ExecuteLoopStateEnum | str,
    ) -> ExecuteLoopState:
        target_state = ExecuteLoopStateEnum(new_state)
        if not self.valid_transition(target_state):
            raise ValueError(
                "Invalid execute-loop transition: "
                f"{self.state.state.value} -> {target_state.value}"
            )

        match target_state:
            case ExecuteLoopStateEnum.OBSERVE:
                self.state = ObserveState()
                self.decision = None
            case ExecuteLoopStateEnum.DECIDE:
                self.state = DecideState()
            case ExecuteLoopStateEnum.ACT:
                self.state = ActState()

        return self.state

    def resolve_decision(
        self,
        decision: ExecuteLoopDecisionEnum | str,
    ) -> ExecuteLoopDecisionEnum:
        if not isinstance(self.state, DecideState):
            raise ValueError(
                "Execute-loop decisions can only be resolved in decide state"
            )

        resolved_decision = ExecuteLoopDecisionEnum(decision)
        self.decision = resolved_decision
        if resolved_decision is ExecuteLoopDecisionEnum.CONTINUE:
            self.perform_transition(ExecuteLoopStateEnum.ACT)

        return resolved_decision
