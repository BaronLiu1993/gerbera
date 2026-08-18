import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from gerbera_harness.memory import Memory


@dataclass(frozen=True)
class ContextBuilder(ABC):
    memory: Memory
    context_window_size: int

    @final
    def build(self) -> list[dict[str, object]]:
        recent_messages = (
            []
            if self.context_window_size == 0
            else self.memory.messages[-self.context_window_size :]
        )
        context_message = {
            "role": "user",
            "content": json.dumps(
                {"runtime_context": self.build_runtime_context()}
            ),
        }
        return [
            context_message,
            *(dict(message) for message in recent_messages),
        ]

    @abstractmethod
    def build_runtime_context(self) -> dict[str, object]:
        raise NotImplementedError
