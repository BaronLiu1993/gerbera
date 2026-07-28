import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor

import pytest

from gerbera_sdk.events.rules import (
    OperatorEnum,
    Rule,
    RuleBuffer,
    RuleBus,
    RuleCallback,
    RuleCondition,
    RuleTriggerModeEnum,
    parse_rule_value,
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
def test_rule_condition_evaluates_supported_operators(
    operator: OperatorEnum,
    actual: float,
    expected: float,
    matches: bool,
) -> None:
    condition = RuleCondition(expected=expected, operator=operator)

    assert condition.evaluate_condition(actual) is matches


def test_rule_condition_does_not_match_missing_value() -> None:
    condition = RuleCondition(
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
def test_parse_rule_value_returns_a_float(value: object, expected: float) -> None:
    parsed = parse_rule_value(value)

    assert parsed == expected
    assert type(parsed) is float


@pytest.mark.parametrize(
    "value",
    ["on", True, False, float("inf"), float("nan")],
)
def test_parse_rule_value_rejects_non_finite_numbers(value: object) -> None:
    with pytest.raises(ValueError, match="finite numbers"):
        parse_rule_value(value)


def test_rule_callback_stores_value_and_returns_callable_result() -> None:
    callback = RuleCallback(
        callback=async_callback(lambda value: value * 2),
        mcp_url=MCP_URL,
    )

    result = asyncio.run(callback(4.0))

    assert result == 8.0
    assert callback.val == 4.0


def test_rule_callback_passes_mcp_url_and_value_to_script() -> None:
    calls: list[tuple[str, float]] = []

    async def script_callback(
        mcp_url: str,
        value: float,
    ) -> dict[str, float]:
        calls.append((mcp_url, value))
        return {"trigger_value": value}

    callback = RuleCallback(
        callback=script_callback,
        mcp_url=MCP_URL,
    )

    result = asyncio.run(callback(1.0))

    assert result == {"trigger_value": 1.0}
    assert callback.val == 1.0
    assert calls == [(MCP_URL, 1.0)]


def test_rule_bus_evaluates_rule_registered_for_event() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=20.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(
                    lambda value: f"high:{value}",
                ),
                mcp_url=MCP_URL,
            ),
        ),
    )

    assert (
        asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 30.0))
        == "high:30.0"
    )


def test_repeat_rule_runs_for_every_matching_event() -> None:
    callback_values: list[float] = []
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=RuleCallback(
                callback=async_callback(
                    lambda value: callback_values.append(value),
                ),
                mcp_url=MCP_URL,
            ),
            trigger_mode=RuleTriggerModeEnum.REPEAT,
        ),
    )

    asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 1.0))
    asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 1.0))

    assert callback_values == [1.0, 1.0]


def test_once_rule_runs_only_for_first_matching_event() -> None:
    callback_values: list[float] = []
    rule = Rule(
        condition=RuleCondition(
            expected=1.0,
            operator=OperatorEnum.EQUAL,
        ),
        callback=RuleCallback(
            callback=async_callback(
                lambda value: callback_values.append(value),
            ),
            mcp_url=MCP_URL,
        ),
        trigger_mode=RuleTriggerModeEnum.ONCE,
    )
    rule_bus = RuleBus()
    rule_bus.register_rule(*EVENT_KEY, rule)

    asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 0.0))
    asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 1.0))
    second_result = asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 1.0)
    )

    assert callback_values == [1.0]
    assert rule.has_triggered is True
    assert second_result is None


def test_once_rule_claim_is_atomic() -> None:
    rule = Rule(
        condition=RuleCondition(
            expected=1.0,
            operator=OperatorEnum.EQUAL,
        ),
        callback=RuleCallback(
            callback=async_callback(lambda value: value),
            mcp_url=MCP_URL,
        ),
        trigger_mode=RuleTriggerModeEnum.ONCE,
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(lambda _: rule.claim_trigger(), range(32)))

    assert claims.count(True) == 1
    assert claims.count(False) == 31


def test_rule_bus_rejects_second_rule_for_same_event() -> None:
    rule_bus = RuleBus()
    rule = Rule(
        condition=RuleCondition(
            expected=20.0,
            operator=OperatorEnum.GREATER_THAN,
        ),
        callback=RuleCallback(
            callback=async_callback(lambda value: value),
            mcp_url=MCP_URL,
        ),
    )
    rule_bus.register_rule(*EVENT_KEY, rule)

    with pytest.raises(ValueError, match="already registered"):
        rule_bus.register_rule(
            *EVENT_KEY,
            Rule(
                condition=RuleCondition(
                    expected=50.0,
                    operator=OperatorEnum.GREATER_THAN,
                ),
                callback=RuleCallback(
                    callback=async_callback(lambda value: value),
                    mcp_url=MCP_URL,
                ),
            ),
        )


def test_rule_bus_returns_none_when_rule_does_not_match() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=50.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(
                    lambda value: f"very-high:{value}",
                ),
                mcp_url=MCP_URL,
            ),
        ),
    )

    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 30.0)
    ) is None


def test_rule_bus_returns_no_results_for_unknown_event() -> None:
    rule_bus = RuleBus()

    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 30.0)
    ) is None


def test_rule_buffer_stores_value_and_emits_rule_evaluation() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=20.0,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(lambda value: value),
                mcp_url=MCP_URL,
            ),
        ),
    )
    rule_buffer = RuleBuffer(rule_bus)
    rule_buffer.register_event_in_buffer(*EVENT_KEY)

    result = asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": "30"})
    )

    assert result == 30.0
    assert rule_buffer.buffer[EVENT_KEY] == 30.0


def test_rule_buffer_does_not_replace_value_when_reregistered() -> None:
    rule_buffer = RuleBuffer(RuleBus())
    rule_buffer.register_event_in_buffer(*EVENT_KEY)
    asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": 10})
    )
    rule_buffer.register_event_in_buffer(*EVENT_KEY)

    assert rule_buffer.buffer[EVENT_KEY] == 10.0


def test_rule_buffer_ignores_unknown_event() -> None:
    rule_buffer = RuleBuffer(RuleBus())

    result = asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": 30})
    )

    assert result is None
    assert rule_buffer.buffer == {}


def test_rule_buffer_rejects_non_numeric_sensor_value() -> None:
    rule_buffer = RuleBuffer(RuleBus())
    rule_buffer.register_event_in_buffer(*EVENT_KEY)

    with pytest.raises(ValueError, match="finite numbers"):
        asyncio.run(
            rule_buffer.update_buffer_value(
                *EVENT_KEY,
                {"value": "on"},
            )
        )

    assert rule_buffer.buffer[EVENT_KEY] is None
