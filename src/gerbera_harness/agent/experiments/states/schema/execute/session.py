from dataclasses import dataclass, field

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.experiments.states.schema.execute.act import (
    ActState,
)
from gerbera_harness.agent.experiments.states.schema.execute.completed import (
    CompletedState,
)
from gerbera_harness.agent.experiments.states.schema.execute.decide import (
    DecideState,
)
from gerbera_harness.agent.experiments.states.schema.execute.incomplete import (
    IncompleteState,
)
from gerbera_harness.agent.experiments.states.schema.execute.observe import (
    ObserveState,
)


@dataclass
class ExecuteLoop:
    state: ExecuteLoopState = field(default_factory=ObserveState)

    def valid_transition(
        self,
        new_state: ExecuteLoopStateEnum | str,
    ) -> bool:
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)

    def perform_transition(
        self,
        new_state: ExecuteLoopStateEnum | str,
    ) -> ExecuteLoopState:
        target_state = ExecuteLoopStateEnum(new_state)
        if not self.state.valid_transition(target_state):
            raise ValueError(
                f"Invalid execute-loop transition: "
                f"{self.state.state.value} -> {target_state.value}"
            )

        match target_state:
            case ExecuteLoopStateEnum.OBSERVE:
                self.state = ObserveState()
            case ExecuteLoopStateEnum.COMPLETED:
                self.state = CompletedState()
            case ExecuteLoopStateEnum.INCOMPLETE:
                self.state = IncompleteState()
            case ExecuteLoopStateEnum.DECIDE:
                self.state = DecideState()
            case ExecuteLoopStateEnum.ACT:
                self.state = ActState()

        return self.state
