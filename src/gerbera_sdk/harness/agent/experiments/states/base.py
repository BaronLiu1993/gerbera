from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar, Collection

from pydantic import BaseModel, RootModel

PROMPT_DIRECTORY = Path(__file__).resolve().parents[3] / "prompts"


class LoopStateEnum(str, Enum):
    INITIALISATION = "initialisation"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    REVIEW = "review"
    COMPLETE = "complete"
    FAILED = "failed"


class DecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TextResponseSchema(RootModel[str]):
    pass


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


@dataclass(frozen=True)
class ExperimentState:
    state: ClassVar[LoopStateEnum]
    prompt_file: ClassVar[str]
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]

    @property
    def prompt_path(self) -> Path:
        return PROMPT_DIRECTORY / self.prompt_file

    @property
    def system_prompt(self) -> str:
        return self.prompt_path.read_text().strip()

    @property
    def prompt(self) -> str:
        return self.system_prompt

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return state in self.valid_transition_states
