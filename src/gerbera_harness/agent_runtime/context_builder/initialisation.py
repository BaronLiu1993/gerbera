from dataclasses import dataclass

from gerbera_harness.agent_runtime.context_builder.base import ContextBuilder


@dataclass(frozen=True)
class InitialisationContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        return {
            "phase": "initialisation",
            "goal": self.memory.goal,
        }
