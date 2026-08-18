from dataclasses import dataclass

from gerbera_harness.runtime.schemas.execution import (
    ExecuteErrorSchema,
)
from gerbera_harness.memory.schemas.events import EventSchema
from gerbera_harness.runtime.context.base import ContextBuilder


@dataclass(frozen=True)
class PlanningContextBuilder(ContextBuilder):
    previous_act_error: ExecuteErrorSchema | None = None

    def build_runtime_context(self) -> dict[str, object]:
        hypothesis = self.memory.current_hypothesis
        current_task = self.memory.get_current_task()
        completed_tasks = self.memory.completed_tasks
        current_world_state = self.memory.latest_world_state()

        return {
            "phase": "planning",
            "goal": self.memory.goal,
            "hypothesis": hypothesis.model_dump(mode="json"),
            "current_step": current_task.model_dump(mode="json"),
            "current_step_goal": current_task.task.goal,
            "current_step_number": self.memory.tasks.index(current_task),
            "current_world_state": (
                current_world_state.model_dump(mode="json")
                if current_world_state
                else None
            ),
            "previous_act_error": (
                self.previous_act_error.model_dump(mode="json")
                if self.previous_act_error is not None
                else None
            ),
            "completed_steps": [
                task.model_dump(mode="json")
                for task in self._recent(completed_tasks)
            ],
            "recent_events": [
                self._serialize_event(event)
                for event in self._recent(self.memory.event_ledger)
            ],
        }

    def _recent(self, values: list) -> list:
        if self.context_window_size == 0:
            return []
        return values[-self.context_window_size:]

    @staticmethod
    def _serialize_event(event: EventSchema) -> dict[str, object]:
        return {
            "id": event.id,
            "event_type": event.event_type.value,
            "source_type": event.source_type.value,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
        }
