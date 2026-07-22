from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import ClassVar, Collection, Optional

from pydantic import BaseModel

PROMPT_DIRECTORY = Path(__file__).resolve().parents[3] / "prompts"


class LoopStateEnum(str, Enum):
    INITIALISATION = "initialisation"
    PLAN = "plan"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    REVIEW = "review"
    COMPLETE = "complete"
    FAILED = "failed"


def build_valid_schema(
    valid_transitions: Collection[LoopStateEnum],
    structured_schema: Optional[type[BaseModel]] = None,
) -> dict:
    response_schema = (
        structured_schema.model_json_schema()
        if structured_schema is not None
        else {"type": "string"}
    )
    definitions = response_schema.pop("$defs", None)

    schema = {
        "type": "object",
        "properties": {
            "next_state": {
                "type": "string",
                "enum": sorted(state.value for state in valid_transitions),
            },
            "response": response_schema,
        },
        "required": ["next_state", "response"],
        "additionalProperties": False,
    }

    if definitions is not None:
        schema["$defs"] = definitions

    return schema


@dataclass(frozen=True)
class ExperimentState:
    state: ClassVar[LoopStateEnum]
    system_prompt: ClassVar[str]
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
    
    @property
    def prompt_path(self) -> Path:
        return PROMPT_DIRECTORY / self.system_prompt

    @property
    def prompt(self) -> str:
        return self.prompt_path.read_text().strip()

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return state in self.valid_transition_states
