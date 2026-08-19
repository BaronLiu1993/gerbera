import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from gerbera_harness.memory import Memory


@dataclass(frozen=True)
class ContextBuilder(ABC):
    memory: Memory
    context_window_size: int

    @abstractmethod
    def build_runtime_context(self) -> dict[str, object]:
        raise NotImplementedError
