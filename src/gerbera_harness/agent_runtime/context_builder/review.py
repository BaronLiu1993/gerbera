from dataclasses import dataclass

from gerbera_harness.agent_runtime.context_builder.base import ContextBuilder
from gerbera_harness.memory import EventSchema


@dataclass(frozen=True)
class ReviewContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        current_task = self.memory.get_current_task()
        completed_tasks = [
            task for task in self.memory.tasks if task.status == "completed"
        ]
        return {
            "phase": "observation",
            "goal": self.memory.goal,
            "hypothesis": (
                hypothesis.model_dump(mode="json")
            ),
            "current_step": current_task.model_dump(mode="json"),
            "completed_steps": [
                task.model_dump(mode="json")
                for task in self._recent(completed_tasks)
            ],
            "errors": [
                error.model_dump(mode="json")
                for error in self._recent(self.memory.errors)
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
