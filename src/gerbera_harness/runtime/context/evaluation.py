from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class EvaluateContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        return {
            "user_intent": self.memory.task_state.user_intent,
            "goal": self.memory.task_state.goal,
            "task_state": self.memory.get_tasks_state().model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "recent_events": [
                event.model_dump(mode="json")
                for event in self.memory.temporal_state.recent_events
            ],
            "recent_world_states": [
                world_state.model_dump(mode="json")
                for world_state in self.memory.temporal_state.recent_world_states
            ],
        }
