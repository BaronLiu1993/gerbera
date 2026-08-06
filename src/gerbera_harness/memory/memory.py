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
    messages: list[dict[str, object]] = field(default_factory=list)
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
        if self.tasks or self.completed_tasks:
            raise RuntimeError("Task lifecycle is already initialized")

        self.tasks.extend(
            TaskSchema(status="pending", task=group)
            for group in hypothesis.method.execute_steps
        )

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
        if task not in self.tasks:
            raise ValueError("Cannot update a task outside main-agent memory")

        if task.status == status:
            return

        task.status = status
        idx = self.tasks.index(task)
        self.append_event(
            event_type=EventTypeEnum.TASK_STATUS_CHANGED,
            source_type=SourceTypeEnum.RUNTIME,
            payload={
                "status": status,
                "step_number": idx,
                "step_goal": task.task.goal,
                "content": task.model_dump(mode="json"),
            },
        )

    def append_message(self, role: str, content: object) -> None:
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
    ) -> EventSchema:
        if task not in self.tasks:
            raise ValueError(
                "Execution result task is not in main-agent memory"
            )
        if not 0 <= position < len(self.tasks):
            raise IndexError("Execution result position is outside task bounds")
        return self.append_event(
            event_type=EventTypeEnum.EXECUTION_RESULT,
            source_type=SourceTypeEnum.RUNTIME,
            payload={
                "decision": decision.value,
                "step_number": position,
                "step_goal": task.task.goal,
                "task": task.model_dump(mode="json"),
                "errors": [error.error for error in errors],
            },
        )

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

    def set_hypothesis(self, hypothesis: HypothesisSchema) -> None:
        self.current_hypothesis = hypothesis
