from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    DecisionEnum,
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)
from gerbera_sdk.harness.agent.experiments.states.schema import HypothesisSchema


@dataclass(frozen=True)
class Initialisation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.INITIALISATION
    system_prompt: ClassVar[str] = "INITIALISATION.md"
    valid_decisions: ClassVar[frozenset[DecisionEnum]] = frozenset(
        {DecisionEnum.ACCEPTED, DecisionEnum.REJECTED}
    )
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.INITIALISATION, LoopStateEnum.EXECUTION}
    )
    valid_schema: ClassVar[dict] = build_valid_schema(
        valid_transition_states,
        HypothesisSchema,
    )
