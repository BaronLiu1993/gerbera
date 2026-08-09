import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor

import pytest

from gerbera_sdk.events.reactions import (
    OperatorEnum,
    Reaction,
    ReactionBuffer,
    ReactionBus,
    ReactionCallback,
    ReactionCondition,
    ReactionTriggerModeEnum,
    parse_reaction_value,
)


EVENT_KEY = ("STREAM", "board-1", "temperature")
MCP_URL = "https://hardware.example.com/mcp"


def async_callback(
    callback: Callable[[float], object],
) -> Callable[[str, float], Awaitable[object]]:
    async def run(mcp_url: str, value: float) -> object:
        return callback(value)

    return run


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "matches"),
    [
        (OperatorEnum.EQUAL, 1.0, 1.0, True),
        (OperatorEnum.NOT_EQUAL, 0.0, 1.0, True),
        (OperatorEnum.LESS_THAN, 9.0, 10.0, True),
        (OperatorEnum.GREATER_THAN, 11.0, 10.0, True),
        (OperatorEnum.LESS_THAN_EQUAL, 10.0, 10.0, True),
        (OperatorEnum.GREATER_THAN_EQUAL, 10.0, 10.0, True),
    ],
)
def test_reaction_condition_evaluates_supported_operators(
    operator: OperatorEnum,
    actual: float,
    expected: float,
    matches: bool,
) -> None:
    condition = ReactionCondition(expected=expected, operator=operator)

    assert condition.evaluate_condition(actual) is matches


def test_reaction_condition_does_not_match_missing_value() -> None:
    condition = ReactionCondition(
        expected=1.0,
        operator=OperatorEnum.NOT_EQUAL,
    )

    assert condition.evaluate_condition(None) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1.0),
        (1, 1.0),
        (1.25, 1.25),
    ],
)
def test_parse_reaction_value_returns_a_float(value: object, expected: float) -> None:
    parsed = parse_reaction_value(value)

    assert parsed == expected
    assert type(parsed) is float


@pytest.mark.parametrize(
    "value",
    ["on", True, False, float("inf"), float("nan")],
)
def test_parse_reaction_value_rejects_non_finite_numbers(value: object) -> None:
    with pytest.raises(ValueError, match="finite numbers"):
        parse_reaction_value(value)


def test_reaction_callback_stores_value_and_returns_callable_result() -> None:
    callback = ReactionCallback(
        callback=async_callback(lambda value: value * 2),
        mcp_url=MCP_URL,
    )

    result = asyncio.run(callback(4.0))

    assert result == 8.0
    assert callback.val == 4.0


def test_reaction_callback_passes_mcp_url_and_value_to_script() -> None:
    calls: list[tuple[str, float]] = []

    async def script_callback(
        mcp_url: str,
        value: float,
    ) -> dict[str, float]:
        calls.append((mcp_url, value))
        return {"trigger_value": value}

    callback = ReactionCallback(
        callback=script_callback,
        mcp_url=MCP_URL,
    )

    result = asyncio.run(callback(1.0))

    assert result == {"trigger_value": 1.0}
    assert callback.val == 1.0
    assert calls == [(MCP_URL, 1.0)]


def test_reaction_bus_evaluates_reaction_registered_for_event() -> None:
    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        *EVENT_KEY,
        Reaction(
            condition=ReactionCondition(
                expected=20.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=ReactionCallback(
                callback=async_callback(
                    lambda value: f"high:{value}",
                ),
                mcp_url=MCP_URL,
            ),
        ),
    )

    assert (
        asyncio.run(reaction_bus.emit_evaluation_event(EVENT_KEY, 30.0))
        == "high:30.0"
    )


def test_repeat_reaction_runs_for_every_matching_event() -> None:
    callback_values: list[float] = []
    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        *EVENT_KEY,
        Reaction(
            condition=ReactionCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=ReactionCallback(
                callback=async_callback(
                    lambda value: callback_values.append(value),
                ),
                mcp_url=MCP_URL,
            ),
            trigger_mode=ReactionTriggerModeEnum.REPEAT,
        ),
    )

    asyncio.run(reaction_bus.emit_evaluation_event(EVENT_KEY, 1.0))
    asyncio.run(reaction_bus.emit_evaluation_event(EVENT_KEY, 1.0))

    assert callback_values == [1.0, 1.0]


def test_once_reaction_runs_only_for_first_matching_event() -> None:
    callback_values: list[float] = []
    reaction = Reaction(
        condition=ReactionCondition(
            expected=1.0,
            operator=OperatorEnum.EQUAL,
        ),
        callback=ReactionCallback(
            callback=async_callback(
                lambda value: callback_values.append(value),
            ),
            mcp_url=MCP_URL,
        ),
        trigger_mode=ReactionTriggerModeEnum.ONCE,
    )
    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(*EVENT_KEY, reaction)

    asyncio.run(reaction_bus.emit_evaluation_event(EVENT_KEY, 0.0))
    asyncio.run(reaction_bus.emit_evaluation_event(EVENT_KEY, 1.0))
    second_result = asyncio.run(
        reaction_bus.emit_evaluation_event(EVENT_KEY, 1.0)
    )

    assert callback_values == [1.0]
    assert reaction.has_triggered is True
    assert second_result is None


def test_once_reaction_claim_is_atomic() -> None:
    reaction = Reaction(
        condition=ReactionCondition(
            expected=1.0,
            operator=OperatorEnum.EQUAL,
        ),
        callback=ReactionCallback(
            callback=async_callback(lambda value: value),
            mcp_url=MCP_URL,
        ),
        trigger_mode=ReactionTriggerModeEnum.ONCE,
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(lambda _: reaction.claim_trigger(), range(32)))

    assert claims.count(True) == 1
    assert claims.count(False) == 31


def test_reaction_bus_rejects_second_reaction_for_same_event() -> None:
    reaction_bus = ReactionBus()
    reaction = Reaction(
        condition=ReactionCondition(
            expected=20.0,
            operator=OperatorEnum.GREATER_THAN,
        ),
        callback=ReactionCallback(
            callback=async_callback(lambda value: value),
            mcp_url=MCP_URL,
        ),
    )
    reaction_bus.register_reaction(*EVENT_KEY, reaction)

    with pytest.raises(ValueError, match="already registered"):
        reaction_bus.register_reaction(
            *EVENT_KEY,
            Reaction(
                condition=ReactionCondition(
                    expected=50.0,
                    operator=OperatorEnum.GREATER_THAN,
                ),
                callback=ReactionCallback(
                    callback=async_callback(lambda value: value),
                    mcp_url=MCP_URL,
                ),
            ),
        )


def test_reaction_bus_returns_none_when_reaction_does_not_match() -> None:
    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        *EVENT_KEY,
        Reaction(
            condition=ReactionCondition(
                expected=50.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=ReactionCallback(
                callback=async_callback(
                    lambda value: f"very-high:{value}",
                ),
                mcp_url=MCP_URL,
            ),
        ),
    )

    assert asyncio.run(
        reaction_bus.emit_evaluation_event(EVENT_KEY, 30.0)
    ) is None


def test_reaction_bus_returns_no_results_for_unknown_event() -> None:
    reaction_bus = ReactionBus()

    assert asyncio.run(
        reaction_bus.emit_evaluation_event(EVENT_KEY, 30.0)
    ) is None


def test_reaction_buffer_stores_value_and_emits_reaction_evaluation() -> None:
    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        *EVENT_KEY,
        Reaction(
            condition=ReactionCondition(
                expected=20.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=ReactionCallback(
                callback=async_callback(lambda value: value),
                mcp_url=MCP_URL,
            ),
        ),
    )
    reaction_buffer = ReactionBuffer(reaction_bus)
    reaction_buffer.register_event_in_buffer(*EVENT_KEY)

    result = asyncio.run(
        reaction_buffer.update_buffer_value(*EVENT_KEY, {"value": "30"})
    )

    assert result == 30.0
    assert reaction_buffer.buffer[EVENT_KEY] == 30.0


def test_reaction_buffer_does_not_replace_value_when_reregistered() -> None:
    reaction_buffer = ReactionBuffer(ReactionBus())
    reaction_buffer.register_event_in_buffer(*EVENT_KEY)
    asyncio.run(
        reaction_buffer.update_buffer_value(*EVENT_KEY, {"value": 10})
    )
    reaction_buffer.register_event_in_buffer(*EVENT_KEY)

    assert reaction_buffer.buffer[EVENT_KEY] == 10.0


def test_reaction_buffer_ignores_unknown_event() -> None:
    reaction_buffer = ReactionBuffer(ReactionBus())

    result = asyncio.run(
        reaction_buffer.update_buffer_value(*EVENT_KEY, {"value": 30})
    )

    assert result is None
    assert reaction_buffer.buffer == {}


def test_reaction_buffer_rejects_non_numeric_sensor_value() -> None:
    reaction_buffer = ReactionBuffer(ReactionBus())
    reaction_buffer.register_event_in_buffer(*EVENT_KEY)

    with pytest.raises(ValueError, match="finite numbers"):
        asyncio.run(
            reaction_buffer.update_buffer_value(
                *EVENT_KEY,
                {"value": "on"},
            )
        )

    assert reaction_buffer.buffer[EVENT_KEY] is None
