from dataclasses import dataclass

from gerbera_harness.workflows.context.base import ContextBuilder


@dataclass(frozen=True)
class ExecutionContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        current_task = self.memory.get_current_task()

        latest_world_state = self.memory.latest_world_state()
        return {
            "phase": "execution",
            "goal": self.memory.goal,
            "hypothesis": hypothesis.model_dump(mode="json"),
            "current_step": current_task.model_dump(mode="json"),
            "current_step_goal": current_task.task.goal,
            "tasks": [
                task.model_dump(mode="json") for task in self.memory.tasks
            ],
            "latest_world_state": (
                latest_world_state.model_dump(mode="json")
                if latest_world_state
                else None
            ),
        }
