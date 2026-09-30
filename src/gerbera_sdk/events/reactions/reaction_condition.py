from dataclasses import dataclass
import math

from gerbera_sdk.events.reactions.reaction_schema import (
    ReactionConditionSchema,
    ReactionOperator,
    ReactionValue,
)

OperatorEnum = ReactionOperator


@dataclass(frozen=True)
class ReactionCondition:
    expected: ReactionValue
    operator: ReactionOperator

    def evaluate_condition(self, actual: object | None) -> bool:
        if actual is None:
            return False
        return reaction_matches(
            ReactionConditionSchema(
                expected_value=self.expected,
                operator=self.operator,
            ),
            actual,
        )


def reaction_matches(
    condition: ReactionConditionSchema,
    actual: object,
) -> bool:
    parsed_value = parse_value_like(actual, condition.expected_value)
    expected_value = condition.expected_value
    comparisons = {
        ReactionOperator.EQUAL: lambda: parsed_value == expected_value,
        ReactionOperator.NOT_EQUAL: lambda: parsed_value != expected_value,
        ReactionOperator.LESS_THAN: lambda: parsed_value < expected_value,
        ReactionOperator.LESS_THAN_EQUAL: lambda: parsed_value <= expected_value,
        ReactionOperator.GREATER_THAN: lambda: parsed_value > expected_value,
        ReactionOperator.GREATER_THAN_EQUAL: lambda: parsed_value >= expected_value,
    }
    return comparisons[condition.operator]()


def parse_value_like(value: object, expected: ReactionValue) -> ReactionValue:
    if isinstance(expected, bool):
        return parse_boolean(value)
    if isinstance(expected, (int, float)):
        return parse_reaction_value(value)
    return str(value)


def parse_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized_value = str(value).strip().casefold()
    if normalized_value in {"1", "true"}:
        return True
    if normalized_value in {"0", "false"}:
        return False
    raise ValueError("Reaction value must be a boolean")


def parse_reaction_value(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Reaction values must be finite numbers")

    try:
        parsed_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Reaction values must be finite numbers") from exc

    if not math.isfinite(parsed_value):
        raise ValueError("Reaction values must be finite numbers")

    return parsed_value
