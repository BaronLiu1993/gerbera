from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Plan(ExperimentState):
    phase: ClassVar[LoopStateEnum] = LoopStateEnum.PLAN
    system_prompt: ClassVar[str] = "PLAN.md"
    valid_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTE}
    )
