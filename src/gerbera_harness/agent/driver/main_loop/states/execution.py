from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    prompt_file: ClassVar[str] = "EXECUTION.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTION, LoopStateEnum.REVIEW}
    )
