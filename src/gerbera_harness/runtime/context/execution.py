from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class ExecutionContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        pass
