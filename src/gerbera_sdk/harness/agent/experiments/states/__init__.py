from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)
from gerbera_sdk.harness.agent.experiments.states.complete import Complete
from gerbera_sdk.harness.agent.experiments.states.execution import Execution
from gerbera_sdk.harness.agent.experiments.states.failed import Failed
from gerbera_sdk.harness.agent.experiments.states.initialisation import Initialisation
from gerbera_sdk.harness.agent.experiments.states.observation import Observation
from gerbera_sdk.harness.agent.experiments.states.review import Review


STATE_REGISTRY: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.INITIALISATION: Initialisation,
    LoopStateEnum.EXECUTION: Execution,
    LoopStateEnum.OBSERVATION: Observation,
    LoopStateEnum.REVIEW: Review,
    LoopStateEnum.COMPLETE: Complete,
    LoopStateEnum.FAILED: Failed,
}


def create_state(state: LoopStateEnum) -> ExperimentState:
    return STATE_REGISTRY[state]()

__all__ = [
    "Complete",
    "Execution",
    "ExperimentState",
    "Failed",
    "Initialisation",
    "LoopStateEnum",
    "Observation",
    "Review",
    "create_state",
]
