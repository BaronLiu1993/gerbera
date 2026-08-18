from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.runtime.subagent.context.base import (
    SubAgentPromptContextBuilder,
)


@dataclass(frozen=True)
class ObservationPromptContextBuilder(SubAgentPromptContextBuilder):
    phase: ClassVar[str] = "observation"
