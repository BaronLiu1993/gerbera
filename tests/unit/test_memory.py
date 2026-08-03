from gerbera_harness.memory import (
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)


def test_memory_has_independent_default_collections() -> None:
    first = Memory(goal="Test the motor")
    second = Memory(goal="Test the heater")

    first.append_message("user", "Observe")

    assert second.messages == []
    assert first.current_hypothesis is None
    assert first.remaining_tasks == []
    assert first.completed_tasks == []


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
