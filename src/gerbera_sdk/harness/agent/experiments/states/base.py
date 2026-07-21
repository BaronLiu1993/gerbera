from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

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
    valid_transition_states: frozenset[LoopStateEnum],
) -> dict:
    return {
        "type": "object",
        "properties": {
            "next_state": {
                "type": "string",
                "enum": sorted(
                    state.value for state in valid_transition_states
                ),
            },
            "response": {"type": "string"},
        },
        "required": ["next_state", "response"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ExperimentState:
    state: ClassVar[LoopStateEnum]
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]]
    valid_schema: ClassVar[dict]
    system_prompt: ClassVar[str]

    @property
    def prompt_path(self) -> Path:
        return PROMPT_DIRECTORY / self.system_prompt

    @property
    def prompt(self) -> str:
        return self.prompt_path.read_text().strip()

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return state in self.valid_transition_states
