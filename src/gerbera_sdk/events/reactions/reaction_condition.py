from dataclasses import dataclass
from enum import Enum
import math


class OperatorEnum(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    LESS_THAN_EQUAL = "less_than_equal"
    GREATER_THAN_EQUAL = "greater_than_equal"


@dataclass
class ReactionCondition:
    expected: float
    operator: OperatorEnum

    def evaluate_condition(self, actual: float | None) -> bool:
        if actual is None:
            return False

        if self.operator == OperatorEnum.EQUAL:
            return actual == self.expected

        if self.operator == OperatorEnum.NOT_EQUAL:
            return actual != self.expected

        if self.operator == OperatorEnum.LESS_THAN:
            return actual < self.expected

        if self.operator == OperatorEnum.GREATER_THAN:
            return actual > self.expected

        if self.operator == OperatorEnum.LESS_THAN_EQUAL:
            return actual <= self.expected

        if self.operator == OperatorEnum.GREATER_THAN_EQUAL:
            return actual >= self.expected

        raise ValueError(f"Unsupported operator: {self.operator}")


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
