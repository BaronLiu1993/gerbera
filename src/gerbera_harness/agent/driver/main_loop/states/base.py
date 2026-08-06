from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import RootModel

PROMPT_DIRECTORY = Path(__file__).resolve().parents[4] / "prompts" / "main"


class LoopStateEnum(str, Enum):
    INITIALISATION = "initialisation"
    EXECUTION = "execution"
    REVIEW = "review"


class InitialisationDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CLARIFY = "clarify"


class TextResponseSchema(RootModel[str]):
    pass


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

    def valid_transition(self, new_state: LoopStateEnum) -> bool:
        return new_state in self.valid_transition_states
