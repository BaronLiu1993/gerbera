from functools import cache
from typing import Collection

from pydantic import BaseModel

from gerbera_harness.agent.experiments.states.base import (
    DecisionEnum,
    ExperimentState,
    LoopStateEnum,
)


def build_valid_schema(
    valid_transitions: Collection[LoopStateEnum],
    structured_schema: type[BaseModel],
) -> dict:
    response_schema = structured_schema.model_json_schema()
    definitions = response_schema.pop("$defs", None)
    response_schema = {
        "anyOf": [response_schema, {"type": "null"}],
    }

    schema = {
        "type": "object",
        "properties": {
            "next_state": {
                "type": "string",
                "enum": sorted(state.value for state in valid_transitions),
            },
            "response": response_schema,
            "decision": {
                "type": "string",
                "enum": [decision.value for decision in DecisionEnum],
            },
        },
        "required": ["next_state", "response", "decision"],
        "additionalProperties": False,
    }

    if definitions is not None:
        schema["$defs"] = definitions

    return schema


@cache
def _state_registry() -> dict[LoopStateEnum, type[ExperimentState]]:
    from gerbera_harness.agent.experiments.states.complete import Complete
    from gerbera_harness.agent.experiments.states.execution import Execution
    from gerbera_harness.agent.experiments.states.failed import Failed
    from gerbera_harness.agent.experiments.states.initialisation import (
        Initialisation,
    )
    from gerbera_harness.agent.experiments.states.review import Review

    return {
        LoopStateEnum.INITIALISATION: Initialisation,
        LoopStateEnum.EXECUTION: Execution,
        LoopStateEnum.REVIEW: Review,
        LoopStateEnum.COMPLETE: Complete,
        LoopStateEnum.FAILED: Failed,
    }


def create_state(state: LoopStateEnum) -> ExperimentState:
    return _state_registry()[state]()
