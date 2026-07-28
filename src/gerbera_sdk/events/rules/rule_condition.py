from dataclasses import dataclass, field
from enum import Enum
import uuid

from pydantic import FiniteFloat, TypeAdapter, ValidationError


_RULE_VALUE_ADAPTER = TypeAdapter(FiniteFloat)


def parse_rule_value(value: object) -> float:
    try:
        return _RULE_VALUE_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError("Rule values must be finite numbers") from exc


class OperatorEnum(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    LESS_THAN_EQUAL = "less_than_equal"
    GREATER_THAN_EQUAL = "greater_than_equal"


@dataclass
class RuleCondition:
    expected: float
    operator: OperatorEnum
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        self.expected = parse_rule_value(self.expected)

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
