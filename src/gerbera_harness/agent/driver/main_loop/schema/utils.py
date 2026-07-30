from typing import Annotated, Collection

from pydantic import BaseModel, ConfigDict, Field

from gerbera_harness.agent.driver.main_loop.states.base import (
    DecisionEnum,
    LoopStateEnum,
)


# Snake Case Enforcement
SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

SnakeCaseVariable = Annotated[
    str,
    Field(
        pattern=SNAKE_CASE_PATTERN,
        description="Lowercase snake_case variable name.",
    ),
]

# Strict Schema so that Unknown Fields Are Validated
class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
