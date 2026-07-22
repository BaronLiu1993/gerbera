from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    system_prompt: ClassVar[str] = "EXECUTION.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.OBSERVATION}
    )
