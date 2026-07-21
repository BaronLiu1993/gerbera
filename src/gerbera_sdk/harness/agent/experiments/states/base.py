from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

PROMPT_DIRECTORY = Path(__file__).resolve().parents[3] / "prompts"


class LoopStateEnum(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"
    COMPLETE = "complete"

@dataclass(frozen=True)
class ExperimentState:
    phase: ClassVar[LoopStateEnum]
    valid_states: ClassVar[frozenset[LoopStateEnum]]
    system_prompt: ClassVar[str]

    @property
    def prompt_path(self) -> Path:
        return PROMPT_DIRECTORY / self.system_prompt

    @property # Do prompt validations here
    def prompt(self) -> str:
        return self.prompt_path.read_text().strip()

    def valid_transition(self, state: LoopStateEnum) -> bool:
        return state in self.valid_states
