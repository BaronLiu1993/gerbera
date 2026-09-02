from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class ObservationContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        physical_configuration = self.memory.physical_configuration

        return {
            "current_task": self.build_current_task_anchor(),
            "task_state": self.memory.get_tasks_state().model_dump(mode="json"),
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "physical_configuration": (
                physical_configuration.model_dump(mode="json")
            ),
            "available_movement_systems": sorted(
                physical_configuration.joint_state_by_movement_system
            ),
            "temporal_state": self.memory.get_temporal_state().model_dump(
                mode="json"
            ),
            "available_tools": self.available_tools,
        }
