from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.initialisation.initialisation_response_schema import (
    InitialisationResponseSchema
)


@dataclass(frozen=True)
class Initialisation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.INITIALISATION
    prompt_file: ClassVar[str] = "INITIALISATION.md"
    valid_decisions: ClassVar[
        frozenset[InitialisationDecisionEnum]
    ] = frozenset(
        {
            InitialisationDecisionEnum.ACCEPTED,
            InitialisationDecisionEnum.REJECTED,
            InitialisationDecisionEnum.CLARIFY,
        }
    )
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.INITIALISATION, LoopStateEnum.EXECUTION}
    )
    valid_schema: ClassVar[dict] = (
        InitialisationResponseSchema.model_json_schema()
    )
    valid_schema["properties"]["next_state"] = {
        "type": "string",
        "enum": sorted(
            state.value for state in valid_transition_states
        ),
    }
    valid_schema["properties"]["decision"] = {
        "type": "string",
        "enum": [
            decision.value
            for decision in InitialisationDecisionEnum
        ],
    }
