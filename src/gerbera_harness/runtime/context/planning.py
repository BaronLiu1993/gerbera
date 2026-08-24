from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class PlanningContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        return {
            "goal": self.memory.task_state.goal,
            "current_task": self.memory.get_current_task_state().model_dump(
                mode="json"
            ),
            "task_state": self.memory.get_tasks_state().model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "recent_events": [
                event.model_dump(mode="json")
                for event in self.memory.temporal_state.recent_events
            ],
        }
