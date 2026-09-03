from dataclasses import dataclass

from gerbera_harness.memory import EventTypeEnum
from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class EvaluateContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        task_state = self.memory.require_task_state()
        return {
            "user_intent": task_state.user_intent,
            "goal": task_state.goal,
            "task_state": task_state.model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "physical_configuration": (
                self.memory.physical_configuration.model_dump(mode="json")
            ),
            "recent_events": [
                event.model_dump(mode="json")
                for event in self.memory.temporal_state.recent_events
            ],
            "recent_world_states": [
                world_state.model_dump(mode="json")
                for world_state in self.memory.temporal_state.recent_world_states
            ],
            "recent_physical_configurations": [
                physical_configuration.model_dump(mode="json")
                for physical_configuration in (
                    self.memory.temporal_state.recent_physical_configurations
                )
            ],
            "task_summaries_by_task_id": (
                self.memory.temporal_state.task_summaries_by_task_id
            ),
            "recent_physical_updates": [
                event.model_dump(mode="json")
                for event in self.memory.get_events_by_type(
                    EventTypeEnum.PHYSICAL_CONFIGURATION_UPDATED
                )
            ],
            "available_tools": self.available_tools,
        }
