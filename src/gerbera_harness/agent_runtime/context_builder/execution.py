from dataclasses import dataclass

from gerbera_harness.agent_runtime.context_builder.base import ContextBuilder


@dataclass(frozen=True)
class ExecutionContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        current_task = self.memory.current_task

        latest_world_state = (
            self.memory.world_state_ledger[-1]
            if self.memory.world_state_ledger
            else None
        )
        return {
            "phase": "execution",
            "goal": self.memory.goal,
            "hypothesis": hypothesis.model_dump(mode="json"),
            "current_step": current_task.model_dump(mode="json"),
            "current_step_goal": current_task.task.goal,
            "remaining_tasks": [
                task.model_dump(mode="json")
                for task in self.memory.remaining_tasks
            ],
            "completed_tasks": [
                task.model_dump(mode="json")
                for task in self.memory.completed_tasks
            ],
            "latest_world_state": (
                latest_world_state.model_dump(mode="json")
                if latest_world_state
                else None
            ),
        }
