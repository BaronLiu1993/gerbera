import asyncio

from mcp.types import ToolAnnotations
from pydantic import ValidationError
import pytest

from gerbera_sdk.events.reactions import (
    CreateReactionSchema,
    ReactionActionSchema,
    ReactionBus,
    ReactionConditionSchema,
    ReactionEventSchema,
    ReactionOperator,
    ReactionTriggerMode,
)
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_store import ReactionStore

EVENT = ReactionEventSchema(
    event_type="STREAM",
    microcontroller_id="board-1",
    event_name="temperature",
    payload_field="value",
)


def make_request(
    *,
    trigger_mode: ReactionTriggerMode = ReactionTriggerMode.CONTINUOUS,
    cooldown_seconds: float = 0,
) -> CreateReactionSchema:
    return CreateReactionSchema(
        event=EVENT,
        condition=ReactionConditionSchema(
            operator=ReactionOperator.GREATER_THAN,
            expected_value=20,
        ),
        action=ReactionActionSchema(
            tool_name="turn_off_heater",
            arguments={"level": 0},
        ),
        trigger_mode=trigger_mode,
        cooldown_seconds=cooldown_seconds,
    )


def make_bus(tmp_path, action) -> ReactionBus:
    registry = ReactionToolRegistry()
    registry.register(
        "turn_off_heater",
        action,
        ToolAnnotations(readOnlyHint=False, openWorldHint=False),
    )
    return ReactionBus(
        action_executor=registry,
        store=ReactionStore(tmp_path),
    )


def test_ordered_condition_rejects_text() -> None:
    with pytest.raises(ValidationError, match="require a number"):
        ReactionConditionSchema(
            operator=ReactionOperator.GREATER_THAN,
            expected_value="hot",
        )


def test_create_list_and_delete_reaction(tmp_path) -> None:
    bus = make_bus(tmp_path, lambda level: {"level": level})

    created = bus.create_reaction(make_request())

    assert bus.list_reactions() == [created]
    assert bus.store.definition_path(created.definition.reaction_id).exists()
    deleted = bus.delete_reaction(created.definition.reaction_id)
    assert deleted == created.definition
    assert bus.list_reactions() == []
    assert not bus.store.definition_path(deleted.reaction_id).exists()


def test_once_reaction_deletes_before_running_action(tmp_path) -> None:
    observations: list[int] = []
    bus: ReactionBus

    def action(level: int) -> dict[str, int]:
        observations.append(len(bus.list_reactions()))
        return {"level": level}

    bus = make_bus(tmp_path, action)
    created = bus.create_reaction(
        make_request(trigger_mode=ReactionTriggerMode.ONCE)
    )

    first = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": "30"})
    )
    second = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": "31"})
    )

    assert first == [{"level": 0}]
    assert second == []
    assert observations == [0]
    assert not bus.store.definition_path(
        created.definition.reaction_id
    ).exists()


def test_continuous_reaction_runs_for_each_matching_event(tmp_path) -> None:
    calls: list[int] = []

    def action(level: int) -> dict[str, int]:
        calls.append(level)
        return {"level": level}

    bus = make_bus(tmp_path, action)
    created = bus.create_reaction(make_request())

    asyncio.run(bus.update_reaction_value(*EVENT.event_key, {"value": 30}))
    asyncio.run(bus.update_reaction_value(*EVENT.event_key, {"value": 31}))

    reaction = bus.get_reaction(created.definition.reaction_id)
    assert calls == [0, 0]
    assert reaction.runtime.trigger_count == 2
    assert reaction.runtime.latest_value == 31
    assert reaction.runtime.last_result == {"level": 0}


def test_once_reaction_stays_deleted_when_action_fails(tmp_path) -> None:
    def fail(level: int) -> None:
        raise RuntimeError("heater unavailable")

    bus = make_bus(tmp_path, fail)
    created = bus.create_reaction(
        make_request(trigger_mode=ReactionTriggerMode.ONCE)
    )

    result = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": 30})
    )

    assert result == []
    assert bus.list_reactions() == []
    assert not bus.store.definition_path(
        created.definition.reaction_id
    ).exists()


def test_continuous_reaction_honors_cooldown(tmp_path) -> None:
    calls: list[int] = []
    bus = make_bus(
        tmp_path,
        lambda level: calls.append(level) or {"level": level},
    )
    bus.create_reaction(make_request(cooldown_seconds=60))

    asyncio.run(bus.update_reaction_value(*EVENT.event_key, {"value": 30}))
    asyncio.run(bus.update_reaction_value(*EVENT.event_key, {"value": 31}))

    assert calls == [0]


def test_multiple_reactions_can_watch_the_same_event(tmp_path) -> None:
    calls: list[int] = []
    bus = make_bus(
        tmp_path,
        lambda level: calls.append(level) or {"level": level},
    )
    bus.create_reaction(make_request())
    bus.create_reaction(make_request())

    results = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": 30})
    )

    assert calls == [0, 0]
    assert results == [{"level": 0}, {"level": 0}]


def test_invalid_event_value_is_reported_without_raising(tmp_path) -> None:
    bus = make_bus(tmp_path, lambda level: {"level": level})
    created = bus.create_reaction(make_request())

    result = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": "hot"})
    )

    reaction = bus.get_reaction(created.definition.reaction_id)
    assert result == []
    assert reaction.runtime.last_error == (
        "Reaction values must be finite numbers"
    )


def test_action_failure_is_reported_without_removing_continuous_reaction(
    tmp_path,
) -> None:
    def fail(level: int) -> None:
        raise RuntimeError("heater unavailable")

    bus = make_bus(tmp_path, fail)
    created = bus.create_reaction(make_request())

    result = asyncio.run(
        bus.update_reaction_value(*EVENT.event_key, {"value": 30})
    )

    reaction = bus.get_reaction(created.definition.reaction_id)
    assert result == []
    assert reaction.runtime.last_error == "heater unavailable"
    assert reaction.runtime.trigger_count == 1


def test_reaction_store_loads_persisted_definitions(tmp_path) -> None:
    bus = make_bus(tmp_path, lambda level: {"level": level})
    created = bus.create_reaction(make_request())

    stored = bus.store.load()

    assert stored == (created.definition,)


def test_tool_registry_rejects_read_only_actions() -> None:
    registry = ReactionToolRegistry()
    registry.register(
        "read_temperature",
        lambda: 20,
        ToolAnnotations(readOnlyHint=True),
    )

    with pytest.raises(ValueError, match="explicitly modify state"):
        registry.validate_action(
            ReactionActionSchema(
                tool_name="read_temperature",
                arguments={},
            )
        )
