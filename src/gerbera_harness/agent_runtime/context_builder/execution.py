from dataclasses import dataclass

from gerbera_harness.agent_runtime.context_builder.base import ContextBuilder


@dataclass(frozen=True)
class ExecutionContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        latest_world_state = (
            self.memory.world_state_ledger[-1]
            if self.memory.world_state_ledger
            else None
        )
        return {
            "phase": "execution",
            "goal": self.memory.goal,
            "hypothesis": (
                hypothesis.model_dump(mode="json") if hypothesis else None
            ),
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
