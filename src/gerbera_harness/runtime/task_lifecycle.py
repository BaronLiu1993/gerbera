from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    TaskSchema,
    TaskStateSchema,
    TaskStatusEnum,
)


@dataclass(frozen=True)
class TaskLifecycleRuntime:
    memory: Memory

    def initialise_tasks(
        self,
        tasks: list[TaskSchema],
        *,
        user_intent: str,
        goal: str,
        success_criteria: list[str],
    ) -> None:
        if not tasks:
            raise ValueError("Task decomposition must contain at least one task")

        self.memory.task_state = TaskStateSchema(
            user_intent=user_intent,
            goal=goal,
            success_criteria=success_criteria,
            tasks=list(tasks),
            current_task_id=tasks[0].task_id,
        )

    def clear_tasks(self) -> None:
        self.memory.task_state = None

    def has_remaining_tasks(self) -> bool:
        task_state = self.memory.require_task_state()
        return any(task.status is TaskStatusEnum.PENDING for task in task_state.tasks)

    def advance_to_next_task(self) -> TaskSchema:
        task_state = self.memory.require_task_state()
        for task in task_state.tasks:
            if task.status is TaskStatusEnum.PENDING:
                task_state.current_task_id = task.task_id
                return task
        raise RuntimeError("No pending task remains")

    def start_current_task(self) -> None:
        task = self.memory.get_current_task_state()
        if task.status is not TaskStatusEnum.PENDING:
            raise ValueError(f"Task cannot start from status: {task.status.value}")
        task.status = TaskStatusEnum.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        self.record_current_task_event(EventTypeEnum.TASK_STARTED)

    def complete_current_task(self) -> None:
        task = self.require_in_progress_task()
        task.status = TaskStatusEnum.COMPLETED
        task.finished_at = datetime.now(timezone.utc)
        self.record_current_task_event(EventTypeEnum.TASK_COMPLETED)

    def fail_current_task(self) -> None:
        task = self.require_in_progress_task()
        task.status = TaskStatusEnum.FAILED
        task.finished_at = datetime.now(timezone.utc)
        self.record_current_task_event(EventTypeEnum.TASK_FAILED)

    def increment_current_task_attempts(self) -> None:
        self.memory.get_current_task_state().attempts += 1

    def require_in_progress_task(self) -> TaskSchema:
        task = self.memory.get_current_task_state()
        if task.status is not TaskStatusEnum.IN_PROGRESS:
            raise ValueError("Task is not in progress")
        return task

    def record_current_task_event(self, event_type: EventTypeEnum) -> None:
        task = self.memory.get_current_task_state()
        self.memory.insert_event(
            EventSchema(
                session_id=self.memory.session_id,
                event_type=event_type,
                source_type=SourceTypeEnum.SYSTEM,
                source_name="task_lifecycle",
                payload=task.model_dump(mode="json"),
                task_id=task.task_id,
            )
        )
        self.memory.rebuild_temporal_state()
