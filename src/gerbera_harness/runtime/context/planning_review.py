from dataclasses import dataclass

from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class PlanningReviewContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        task = self.get_task()
        task_payload = task.model_dump(mode="json")
        physical_configuration = self.memory.physical_configuration

        return {
            "current_task": {
                "task_id": task_payload["task_id"],
                "task_goal": task_payload["task_goal"],
                "success_criteria": task_payload["success_criteria"],
                "status": task_payload["status"],
                "attempts": task_payload["attempts"],
            },
            "world_state": self.memory.world_state.model_dump(mode="json"),
            "physical_configuration": (
                physical_configuration.model_dump(mode="json")
            ),
            "available_movement_systems": sorted(
                physical_configuration.joint_state_by_movement_system
            ),
            "available_tools": self.available_tools,
        }
