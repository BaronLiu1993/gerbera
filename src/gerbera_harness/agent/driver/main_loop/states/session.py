from dataclasses import dataclass, field
import uuid

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.states.execution import (
    Execution,
)
from gerbera_harness.agent.driver.main_loop.states.initialisation import (
    Initialisation,
)
from gerbera_harness.agent.driver.main_loop.states.review import (
    Review,
)


STATE_TYPES: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.INITIALISATION: Initialisation,
    LoopStateEnum.EXECUTION: Execution,
    LoopStateEnum.REVIEW: Review,
}


@dataclass
class Session:
    state: ExperimentState = field(default_factory=Initialisation)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def valid_transition(
        self,
        new_state: LoopStateEnum | str,
    ) -> bool:
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
