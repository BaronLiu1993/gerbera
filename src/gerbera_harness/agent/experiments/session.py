from dataclasses import dataclass, field
import uuid

from gerbera_sdk.harness.agent.experiments.states import (
    ExperimentState,
    Initialisation,
    LoopStateEnum,
)
from gerbera_sdk.harness.agent.experiments.states.utils import create_state


@dataclass
class Session:
    state: ExperimentState = field(default_factory=Initialisation)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

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

        self.state = create_state(target_state)
        return self.state
