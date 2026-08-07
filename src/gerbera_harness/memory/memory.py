import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import JsonValue

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.memory.event_schema import (
    EventSchema,
    EventTypeEnum,
    SourceTypeEnum,
)
from gerbera_harness.memory.task_schema import TaskSchema
from gerbera_harness.memory.world_state_schema import WorldStateSchema


@dataclass
class Memory:
    goal: str
    # The workflow orchestrator should set this to the main agent run_id.
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[dict[str, str]] = field(default_factory=list)
    current_hypothesis: HypothesisSchema | None = None
    tasks: list[TaskSchema] = field(default_factory=list)
    # Owned by the main-agent execution lifecycle. Subagents may read this
    # context, but only the main execution runtime marks workflow completion.
    completed_tasks: list[TaskSchema] = field(default_factory=list)
    event_ledger: list[EventSchema] = field(default_factory=list)
    world_state_ledger: list[WorldStateSchema] = field(
        default_factory=list
    )

    def get_current_task(self) -> TaskSchema | None:
        for task in self.tasks:
            if task.status == "in_progress":
                return task

    def initialize_tasks(self, hypothesis: HypothesisSchema) -> None:
        if self.tasks:
            raise RuntimeError("Tasks are already initialized")

        for group in hypothesis.method.execute_steps:
            self.tasks.append(TaskSchema(status="pending", task=group))

    def start_task(self, task: TaskSchema) -> None:
        current_task = self.get_current_task()
        if current_task is not None and current_task is not task:
            raise RuntimeError("Another task is already in progress")
        self._set_task_status(task, "in_progress")

    def complete_task(self, task: TaskSchema) -> None:
        self._set_task_status(task, "completed")
        if task not in self.completed_tasks:
            self.completed_tasks.append(task)

    def fail_task(self, task: TaskSchema) -> None:
        self._set_task_status(task, "failed")
        if task in self.completed_tasks:
            self.completed_tasks.remove(task)

    def _set_task_status(
        self,
        task: TaskSchema,
        status: Literal["in_progress", "completed", "failed"],
    ) -> None:
        position = self.tasks.index(task)

        task.status = status
        self.append_event(
            event_type=EventTypeEnum.TASK_STATUS_CHANGED,
            source_type=SourceTypeEnum.RUNTIME,
            payload={
                "status": status,
                "step_number": position,
                "step_goal": task.task.goal,
                "content": task.model_dump(mode="json"),
            },
        )

    def append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def append_event(
        self,
        *,
        event_type: EventTypeEnum,
        source_type: SourceTypeEnum,
        payload: dict[str, Any],
    ) -> EventSchema:
        event = EventSchema(
            event_type=event_type,
            source_type=source_type,
            payload=payload,
            session_id=self.session_id,
        )
        self.event_ledger.append(event)
        return event

    def append_execution_result(
        self,
        *,
        task: TaskSchema,
        position: int,
        decision: ExecuteDecisionEnum,
        errors: list[ExecuteErrorSchema],
        observations: list[WorldStateSchema],
        tool_events: list[dict[str, object]],
    ) -> EventSchema:
        task_position = self.tasks.index(task)
        if task_position != position:
            raise IndexError("Execution result position is outside task bounds")

        committed_errors: list[ExecuteErrorSchema] = []
        if decision is ExecuteDecisionEnum.REJECTED:
            committed_errors = list(errors)

        events: list[EventSchema] = []
        for tool_event in tool_events:
            events.append(
                EventSchema(
                    event_type=EventTypeEnum.TOOL_CALL,
                    source_type=SourceTypeEnum.MCP_TOOL,
                    payload=dict(tool_event),
                    session_id=self.session_id,
                )
            )

        for observation in observations:
            events.append(
                EventSchema(
                    event_type=EventTypeEnum.WORLD_STATE_UPDATED,
                    source_type=SourceTypeEnum.MODEL,
                    payload={
                        "world_state": observation.model_dump(mode="json")
                    },
                    session_id=self.session_id,
                )
            )

        error_messages: list[str] = []
        for error in committed_errors:
            error_messages.append(error.error)

        result_event = EventSchema(
            event_type=EventTypeEnum.EXECUTION_RESULT,
            source_type=SourceTypeEnum.RUNTIME,
            payload={
                "decision": decision.value,
                "step_number": position,
                "step_goal": task.task.goal,
                "task": task.model_dump(mode="json"),
                "errors": error_messages,
            },
            session_id=self.session_id,
        )
        events.append(result_event)

        self.world_state_ledger.extend(observations)
        self.event_ledger.extend(events)
        return result_event

    def append_world_state(
        self,
        state: dict[str, JsonValue],
    ) -> WorldStateSchema:
        world_state = WorldStateSchema(
            observed_at=datetime.now(timezone.utc),
            state=state,
        )
        self.world_state_ledger.append(world_state)
        return world_state
