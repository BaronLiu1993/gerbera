from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.memory import (
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    TaskSchema,
)


def current_task() -> TaskSchema:
    return TaskSchema.model_validate(
        {
            "status": "in_progress",
            "task": {
                "goal": "Set the motor speed to 10",
                "action_type": "execute",
                "actions": [
                    {
                        "description": "Set the motor speed",
                        "action_type": "execute",
                        "execution_type": "discrete",
                        "start_offset_seconds": 0,
                        "dependent_variables": ["motor_speed"],
                        "independent_variables": ["requested_speed"],
                        "forward_tool_call": "set_motor",
                        "params": [],
                    }
                ],
            },
        }
    )


def test_memory_has_independent_default_collections() -> None:
    first = Memory(goal="Test the motor")
    second = Memory(goal="Test the heater")

    first.append_message("user", "Observe")

    assert second.messages == []
    assert first.current_hypothesis is None
    assert first.tasks == []
    assert first.completed_tasks == []


def test_failed_task_is_removed_from_completed_tasks() -> None:
    memory = Memory(goal="Set the motor speed")
    task = current_task()
    memory.tasks.append(task)

    memory.complete_task(task)
    memory.fail_task(task)

    assert task.status == "failed"
    assert memory.completed_tasks == []
    assert [event.payload["status"] for event in memory.event_ledger] == [
        "completed",
        "failed",
    ]


def test_memory_returns_none_without_current_task() -> None:
    memory = Memory(goal="Test the motor")

    assert memory.get_current_task() is None


def test_initialise_tasks_creates_pending_lifecycle_once() -> None:
    memory = Memory(goal="Run the motor workflow")
    first = current_task().task
    second = first.model_copy(update={"goal": "Set speed to 20"})
    hypothesis = SimpleNamespace(
        method=SimpleNamespace(execute_steps=[first, second])
    )

    memory.initialize_tasks(hypothesis)

    assert [task.task for task in memory.tasks] == [first, second]
    assert [task.status for task in memory.tasks] == ["pending", "pending"]
    assert memory.completed_tasks == []
    assert memory.get_current_task() is None

    with pytest.raises(RuntimeError, match="already initialized"):
        memory.initialize_tasks(hypothesis)


def test_tasks_have_independent_application_owned_ids() -> None:
    first = current_task()
    second = current_task()

    assert first.id
    assert second.id
    assert first.id != second.id


def test_complete_task_moves_the_current_task_and_records_event() -> None:
    memory = Memory(goal="Set the motor speed")
    task = current_task()
    memory.tasks.append(task)

    result = memory.complete_task(task)

    assert result is None
    assert memory.tasks == [task]
    assert memory.tasks[0].status == "completed"
    assert memory.completed_tasks == [task]
    assert memory.event_ledger[-1].event_type is (
        EventTypeEnum.TASK_STATUS_CHANGED
    )
    assert memory.event_ledger[-1].payload["step_goal"] == (
        "Set the motor speed to 10"
    )


def test_memory_stores_events_and_world_states() -> None:
    memory = Memory(goal="Measure the temperature")
    event = memory.append_event(
        event_type=EventTypeEnum.TOOL_CALL,
        source_type=SourceTypeEnum.MCP_TOOL,
        payload={
            "tool_name": "read_temperature",
            "result": {"value": 22.5, "unit": "celsius"},
        },
    )
    world_state = memory.append_world_state(
        {"temperature": {"value": 22.5, "unit": "celsius"}}
    )

    assert event.session_id == memory.session_id
    assert world_state is memory.world_state_ledger[-1]
    assert memory.event_ledger[-1].payload["tool_name"] == (
        "read_temperature"
    )
    assert memory.world_state_ledger[-1].state["temperature"] == {
        "value": 22.5,
        "unit": "celsius",
    }


def test_execution_result_commits_evidence_and_errors_together() -> None:
    memory = Memory(goal="Set the motor speed")
    task = current_task()
    memory.tasks.append(task)
    error = ExecuteErrorSchema(
        event_name="set_motor",
        event_type=ExecutionTypeEnum.DISCRETE,
        position=0,
        error="Motor rejected command",
    )
    tool_event = {
        "position": 0,
        "tool_name": "set_motor",
        "arguments": {"speed": 10},
        "status": "failed",
        "result": None,
    }

    result = memory.append_execution_result(
        task=task,
        position=0,
        decision=ExecuteDecisionEnum.REJECTED,
        errors=[error],
        observations=[],
        tool_events=[tool_event],
    )

    assert [event.event_type for event in memory.event_ledger] == [
        EventTypeEnum.TOOL_CALL,
        EventTypeEnum.EXECUTION_RESULT,
    ]
    assert memory.event_ledger[0].payload == tool_event
    assert result.payload["errors"] == ["Motor rejected command"]


def test_execution_commit_validates_before_writing_evidence() -> None:
    memory = Memory(goal="Set the motor speed")
    task = current_task()
    memory.tasks.append(task)

    with pytest.raises(IndexError):
        memory.append_execution_result(
            task=task,
            position=1,
            decision=ExecuteDecisionEnum.REJECTED,
            errors=[],
            observations=[],
            tool_events=[{"tool_name": "set_motor"}],
        )

    assert memory.event_ledger == []
