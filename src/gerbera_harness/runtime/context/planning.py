from dataclasses import dataclass

from gerbera_harness.memory import EventTypeEnum
from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class PlanningContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        task_state = self.memory.require_task_state()
        return {
            "goal": task_state.goal,
            "current_task": self.build_current_task_anchor(),
            "task_state": task_state.model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "recent_events": [
                event.model_dump(mode="json")
                for event in self.memory.temporal_state.recent_events
            ],
            "recent_world_updates": [
                event.model_dump(mode="json")
                for event in self.memory.get_events_by_type(
                    EventTypeEnum.WORLD_STATE_UPDATED
                )
            ],
        }
