from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class ObservationContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        return {
            "current_task": self.build_current_task_anchor(),
            "task_state": self.memory.get_tasks_state().model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "temporal_state": self.memory.get_temporal_state().model_dump(
                mode="json"
            ),
        }
