from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)


@dataclass(frozen=True)
class Hypothesize(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.HYPOTHESIZE
    system_prompt: ClassVar[str] = "HYPOTHESIZE.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.PLAN}
    )
    valid_schema: ClassVar[dict] = build_valid_schema(valid_transition_states)
