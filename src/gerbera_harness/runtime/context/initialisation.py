from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class InitialisationContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        pass
