import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from gerbera_sdk.rule_engine import (
    OperatorEnum,
    Rule,
    RuleBuffer,
    RuleBus,
    RuleCallback,
    RuleCondition,
    RuleValue,
)


EVENT_KEY = ("STREAM", "board-1", "temperature")


def async_callback(
    callback: Callable[[RuleValue], Any],
) -> Callable[[RuleValue], Awaitable[Any]]:
    async def run(value: RuleValue) -> Any:
        return callback(value)

    return run


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "matches"),
    [
        (OperatorEnum.EQUAL, "on", "on", True),
        (OperatorEnum.NOT_EQUAL, "off", "on", True),
        (OperatorEnum.LESS_THAN, "9", 10, True),
        (OperatorEnum.GREATER_THAN, 11, "10", True),
        (OperatorEnum.LESS_THAN_EQUAL, 10, 10, True),
        (OperatorEnum.GREATER_THAN_EQUAL, 10, 10, True),
    ],
)
def test_rule_condition_evaluates_supported_operators(
    operator: OperatorEnum,
    actual: RuleValue,
    expected: RuleValue,
    matches: bool,
) -> None:
    condition = RuleCondition(expected=expected, operator=operator)

    assert condition.evaluate_condition(actual) is matches


def test_rule_condition_does_not_match_missing_value() -> None:
    condition = RuleCondition(
        expected="on",
        operator=OperatorEnum.NOT_EQUAL,
    )

    assert condition.evaluate_condition(None) is False


def test_rule_condition_rejects_non_numeric_values() -> None:
    condition = RuleCondition(
        expected=10,
        operator=OperatorEnum.GREATER_THAN,
    )

    with pytest.raises(ValueError, match="to be numeric"):
        condition.evaluate_condition("not-a-number")


def test_rule_callback_stores_value_and_returns_callable_result() -> None:
    callback = RuleCallback(
        callback=async_callback(lambda value: value * 2),
    )

    result = asyncio.run(callback(4))

    assert result == 8
    assert callback.val == 4


def test_rule_bus_evaluates_rule_registered_for_event() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=20,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(
                    lambda value: f"high:{value}",
                ),
            ),
        ),
    )

    assert (
        asyncio.run(rule_bus.emit_evaluation_event(EVENT_KEY, 30))
        == "high:30"
    )


def test_rule_bus_rejects_second_rule_for_same_event() -> None:
    rule_bus = RuleBus()
    rule = Rule(
        condition=RuleCondition(
            expected=20,
            operator=OperatorEnum.GREATER_THAN,
        ),
        callback=RuleCallback(
            callback=async_callback(lambda value: value),
        ),
    )
    rule_bus.register_rule(*EVENT_KEY, rule)

    with pytest.raises(ValueError, match="already registered"):
        rule_bus.register_rule(
            *EVENT_KEY,
            Rule(
                condition=RuleCondition(
                    expected=50,
                    operator=OperatorEnum.GREATER_THAN,
                ),
                callback=RuleCallback(
                    callback=async_callback(lambda value: value),
                ),
            ),
        )


def test_rule_bus_returns_none_when_rule_does_not_match() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=50,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(
                    lambda value: f"very-high:{value}",
                ),
            ),
        ),
    )

    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 30)
    ) is None


def test_rule_bus_returns_no_results_for_unknown_event() -> None:
    rule_bus = RuleBus()

    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 30)
    ) is None


def test_rule_buffer_stores_value_and_emits_rule_evaluation() -> None:
    rule_bus = RuleBus()
    rule_bus.register_rule(
        *EVENT_KEY,
        Rule(
            condition=RuleCondition(
                expected=20,
                operator=OperatorEnum.GREATER_THAN,
            ),
            callback=RuleCallback(
                callback=async_callback(lambda value: value),
            ),
        ),
    )
    rule_buffer = RuleBuffer(rule_bus)
    rule_buffer.register_event_in_buffer(*EVENT_KEY)

    result = asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": 30})
    )

    assert result == 30
    assert rule_buffer.read_buffer_value(*EVENT_KEY) == 30


def test_rule_buffer_does_not_replace_value_when_reregistered() -> None:
    rule_buffer = RuleBuffer(RuleBus())
    rule_buffer.register_event_in_buffer(*EVENT_KEY)
    asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": 10})
    )
    rule_buffer.register_event_in_buffer(*EVENT_KEY)

    assert rule_buffer.read_buffer_value(*EVENT_KEY) == 10


def test_rule_buffer_ignores_unknown_event() -> None:
    rule_buffer = RuleBuffer(RuleBus())

    result = asyncio.run(
        rule_buffer.update_buffer_value(*EVENT_KEY, {"value": 30})
    )

    assert result is None
    assert rule_buffer.buffer == {}
