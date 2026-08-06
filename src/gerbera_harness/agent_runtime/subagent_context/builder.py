import json
from dataclasses import dataclass
from typing import Literal

from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)
from gerbera_harness.agent_runtime.subagent_context.context import (
    SubAgentContext,
)
from gerbera_harness.memory import Memory, TaskSchema, WorldStateSchema


@dataclass(frozen=True)
class SubAgentContextBuilder:
    memory: Memory
    context_window_size: int = 20

    def build(
        self,
        *,
        current_task: TaskSchema,
        workflow_position: int,
    ) -> SubAgentContext:
        hypothesis = self.memory.current_hypothesis
        if hypothesis is None:
            raise RuntimeError("Subagent execution requires a hypothesis")
        if current_task not in self.memory.tasks:
            raise ValueError("Subagent task is not in main-agent memory")
        if workflow_position < 0:
            raise ValueError("Subagent workflow position must be non-negative")

        return SubAgentContext(
            goal=self.memory.goal,
            hypothesis=hypothesis,
            current_task=current_task.task,
            workflow_position=workflow_position,
            completed_tasks=tuple(
                self._recent(self.memory.completed_tasks)
            ),
            world_states=tuple(
                self._recent(self.memory.world_state_ledger)
            ),
            relevant_events=tuple(
                self._recent(self.memory.event_ledger)
            ),
        )

    def _recent(self, values: list) -> list:
        if self.context_window_size == 0:
            return []
        return values[-self.context_window_size :]


@dataclass(frozen=True)
class SubAgentPromptContextBuilder:
    context: SubAgentContext
    phase: Literal["observation", "planning"]
    messages: list[dict[str, object]]
    observations: list[WorldStateSchema]
    tool_events: list[dict[str, object]]
    context_window_size: int = 20
    previous_act_error: ExecuteErrorSchema | None = None

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
                {
                    "event_type": event.event_type.value,
                    "source_type": event.source_type.value,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                }
                for event in self.context.relevant_events
            ],
            "tool_events": [
                dict(event) for event in self.tool_events
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
        recent_messages = self._recent(self.messages)
        return [context_message, *(dict(message) for message in recent_messages)]

    def _recent(self, values: list) -> list:
        if self.context_window_size == 0:
            return []
        return values[-self.context_window_size :]
