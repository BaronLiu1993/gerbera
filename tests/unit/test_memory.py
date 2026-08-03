from datetime import datetime, timezone

from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    WorldStateSchema,
)


def test_memory_has_independent_default_collections() -> None:
    first = Memory()
    second = Memory()

    first.messages.append({"role": "user", "content": "Observe"})

    assert second.messages == []
    assert first.current_hypothesis is None
    assert first.remaining_tasks == []
    assert first.completed_tasks == []


def test_memory_stores_events_and_world_states() -> None:
    memory = Memory()
    observed_at = datetime.now(timezone.utc)

    memory.event_ledger.append(
        EventSchema(
            event_type=EventTypeEnum.TOOL_CALL,
            source_type=SourceTypeEnum.MCP_TOOL,
            payload={
                "tool_name": "read_temperature",
                "result": {"value": 22.5, "unit": "celsius"},
            },
            session_id="session-1",
        )
    )
    memory.world_state_ledger.append(
        WorldStateSchema(
            observed_at=observed_at,
            state={"temperature": {"value": 22.5, "unit": "celsius"}},
        )
    )

    assert memory.event_ledger[-1].payload["tool_name"] == (
        "read_temperature"
    )
    assert memory.world_state_ledger[-1].state["temperature"] == {
        "value": 22.5,
        "unit": "celsius",
    }
