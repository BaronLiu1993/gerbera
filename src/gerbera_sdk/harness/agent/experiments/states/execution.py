from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.harness.agent.experiments.states.base import (
    DecisionEnum,
    ExperimentState,
    LoopStateEnum,
)


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    prompt_file: ClassVar[str] = "EXECUTION.md"
    valid_decisions: ClassVar[frozenset[DecisionEnum]] = frozenset(
        {DecisionEnum.ACCEPTED, DecisionEnum.REJECTED}
    )
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTION, LoopStateEnum.REVIEW}
    )
    # It will be action successful or unsuccessful and that is it
    # valid_schema: ClassVar[dict] = build_valid_schema(
    #     valid_transition_states,
    #     ExecutionSchema,
    # )
