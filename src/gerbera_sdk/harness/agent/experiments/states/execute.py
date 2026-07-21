from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)


@dataclass(frozen=True)
class Execute(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTE
    system_prompt: ClassVar[str] = "EXECUTE.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.OBSERVE}
    )
    valid_schema: ClassVar[dict] = build_valid_schema(valid_transition_states)
