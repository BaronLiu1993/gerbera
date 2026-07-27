from dataclasses import dataclass, field
import uuid

from gerbera_sdk.harness.agent.experiments.states import (
    ExperimentState,
    Initialisation,
    LoopStateEnum,
)


@dataclass
class Session:
    state: ExperimentState = field(default_factory=Initialisation)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def valid_transition(self, new_state: LoopStateEnum) -> bool:
        return self.state.valid_transition(new_state)

    def perform_transition(self, new_state: LoopStateEnum):
        if self.valid_transition(new_state):
            self.state = new_state
        else:
            raise ValueError("Invalid Transition.")

