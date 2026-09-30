import pytest

from gerbera_harness.memory import (
    EventStateSchema,
    EventTypeEnum,
    Memory,
    PhysicalConfigurationStateSchema,
    TaskSchema,
    TaskStatusEnum,
    TemporalStateSchema,
    WorldStateSchema,
)
from gerbera_harness.runtime.task_lifecycle import TaskLifecycleRuntime


def build_memory() -> Memory:
    session_id = "session-1"
    return Memory(
        session_id=session_id,
        world_state=WorldStateSchema(session_id=session_id),
        temporal_state=TemporalStateSchema(session_id=session_id),
        task_state=None,
        events_state=EventStateSchema(session_id=session_id),
        physical_configuration=PhysicalConfigurationStateSchema(
            session_id=session_id
        ),
    )


def test_task_lifecycle_records_started_and_completed_events() -> None:
    memory = build_memory()
    lifecycle = TaskLifecycleRuntime(memory)
    task = TaskSchema(
        task_goal="Inspect the workspace",
        success_criteria=["Workspace inspected"],
        status=TaskStatusEnum.PENDING,
        session_id=memory.session_id,
    )
    lifecycle.initialise_tasks(
        [task],
        user_intent="Inspect",
        goal="Understand the workspace",
        success_criteria=["Inspection completed"],
    )

    lifecycle.start_current_task()
    lifecycle.complete_current_task()

    assert task.status is TaskStatusEnum.COMPLETED
    assert task.started_at is not None
    assert task.finished_at is not None
    assert [event.event_type for event in memory.get_events_state()] == [
        EventTypeEnum.TASK_STARTED,
        EventTypeEnum.TASK_COMPLETED,
    ]


def test_task_lifecycle_rejects_empty_task_decomposition() -> None:
    lifecycle = TaskLifecycleRuntime(build_memory())

    with pytest.raises(
        ValueError,
        match="Task decomposition must contain at least one task",
    ):
        lifecycle.initialise_tasks(
            [],
            user_intent="Inspect",
            goal="Understand the workspace",
            success_criteria=[],
        )
