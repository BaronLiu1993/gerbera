import json
from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.runtime.schemas.execution import ExecuteErrorSchema
from gerbera_harness.memory.schemas.events import EventSchema
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.runtime.subagent.context.models import SubAgentContext
from gerbera_harness.tools.base import ToolSpec


@dataclass(frozen=True)
class SubAgentPromptContextBuilder:
    phase: ClassVar[str]

    context: SubAgentContext
    messages: list[dict[str, object]]
    observations: list[WorldStateSchema]
    tool_events: list[dict[str, object]]
    context_window_size: int = 20
    previous_act_error: ExecuteErrorSchema | None = None
    available_tools: tuple[ToolSpec, ...] = ()

    def build(self) -> list[dict[str, object]]:
        runtime_context = {
            "phase": self.phase,
            "goal": self.context.goal,
            "hypothesis": self.context.hypothesis.model_dump(mode="json"),
            "current_step": self.context.current_task.model_dump(mode="json"),
            "current_step_goal": self.context.current_task.goal,
            "current_step_number": self.context.workflow_position,
            "completed_steps": [
                task.model_dump(mode="json")
                for task in self.context.completed_tasks
            ],
            "world_states": [
                state.model_dump(mode="json")
                for state in (*self.context.world_states, *self.observations)
            ],
            "relevant_events": [
                self._serialize_event(event)
                for event in self.context.relevant_events
            ],
            "tool_events": [
                dict(event) for event in self.tool_events
            ],
            "available_tools": [
                tool.model_dump() for tool in self.available_tools
            ],
            "previous_act_error": (
                self.previous_act_error.model_dump(mode="json")
                if self.previous_act_error is not None
                else None
            ),
        }
        context_message = {
            "role": "user",
            "content": json.dumps({"runtime_context": runtime_context}),
        }
        return [
            context_message,
            *(dict(message) for message in self._recent(self.messages)),
        ]

    def _recent(self, values: list) -> list:
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
