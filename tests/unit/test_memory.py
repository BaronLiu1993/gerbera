from gerbera_harness.memory import (
    ExecuteErrorSchema,
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
    assert second.errors == []


def test_memory_returns_none_without_current_task() -> None:
    memory = Memory(goal="Test the motor")

    assert memory.get_current_task() is None


def test_complete_task_moves_the_current_task_and_records_event() -> None:
    memory = Memory(goal="Set the motor speed")
    task = current_task()
    memory.tasks.append(task)

    result = memory.complete_task()

    assert result is None
    assert memory.tasks == [task]
    assert memory.tasks[0].status == "completed"
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


def test_memory_appends_error_for_current_task() -> None:
    memory = Memory(goal="Set the motor speed")
    error = ExecuteErrorSchema(
        event_name="Set the motor speed",
        event_type="discrete",
        position=0,
        error="motor rejected command",
    )

    result = memory.append_errors([error])

    assert result is None
    assert memory.errors == [error]
    assert error.error == "motor rejected command"
