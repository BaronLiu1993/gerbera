from dataclasses import dataclass, field
import uuid

from gerbera_harness.agent.experiments.states import (
    Complete,
    Execution,
    ExperimentState,
    Failed,
    Initialisation,
    LoopStateEnum,
    Review,
)


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

        match target_state:
            case LoopStateEnum.INITIALISATION:
                self.state = Initialisation()
            case LoopStateEnum.EXECUTION:
                self.state = Execution()
            case LoopStateEnum.REVIEW:
                self.state = Review()
            case LoopStateEnum.COMPLETE:
                self.state = Complete()
            case LoopStateEnum.FAILED:
                self.state = Failed()

        return self.state
