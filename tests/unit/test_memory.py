from datetime import datetime, timezone

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.event_schema import (
    EventSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.world_state_schema import (
    WorldStateSchema,
)
from gerbera_harness.memory import Memory


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
            event_type="tool_call",
            event_name="read_temperature",
            event_description="Read the current temperature.",
            event_status="success",
            occurred_at=observed_at,
            result={"value": 22.5, "unit": "celsius"},
        )
    )
    memory.world_state_ledger.append(
        WorldStateSchema(
            observed_at=observed_at,
            state={"temperature": {"value": 22.5, "unit": "celsius"}},
        )
    )

    assert memory.event_ledger[-1].event_name == "read_temperature"
    assert memory.world_state_ledger[-1].state["temperature"] == {
        "value": 22.5,
        "unit": "celsius",
    }
