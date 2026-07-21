from dataclasses import dataclass, field
import uuid

from gerbera_sdk.harness.agent.experiments.states import (
    ExperimentState,
    LoopStateEnum,
    Plan,
)


@dataclass
class Session:
    state: ExperimentState = field(default_factory=Plan)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def phase(self) -> LoopStateEnum:
        return self.state.phase

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return self.state.valid_transition(state)


