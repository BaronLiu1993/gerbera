from dataclasses import dataclass

from gerbera_harness.agent_runtime.context_builder.base import ContextBuilder
from gerbera_harness.memory import EventSchema


@dataclass(frozen=True)
class ReviewContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        current_task = self.memory.current_task

        return {
            "phase": "observation",
            "goal": self.memory.goal,
            "hypothesis": (
                hypothesis.model_dump(mode="json") if hypothesis else None
            ),
            "current_step": (
                current_task.model_dump(mode="json")
                if current_task
                else None
            ),
            "current_step_goal": (
                current_task.task.goal if current_task else None
            ),
            "current_step_number": (
                len(self.memory.completed_tasks) + 1
                if current_task
                else None
            ),
            "completed_steps": [
                task.model_dump(mode="json")
                for task in self._recent(self.memory.completed_tasks)
            ],
            "recent_events": [
                self._serialize_event(event)
                for event in self._recent(self.memory.event_ledger)
            ],
            "previous_world_states": [
                state.model_dump(mode="json")
                for state in self._recent(self.memory.world_state_ledger)
            ],
        }

    def _recent(self, values: list[str]) -> list[str]:
        if self.context_window_size == 0:
            return []
        return values[-self.context_window_size :]

    @staticmethod
    def _serialize_event(event: EventSchema) -> dict[str, object]:
        return {
            "id": event.id,
            "event_type": event.event_type.value,
            "source_type": event.source_type.value,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
        }
