from dataclasses import dataclass, field
from enum import Enum
import uuid


RuleValue = bool | int | float | str


class OperatorEnum(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    LESS_THAN_EQUAL = "less_than_equal"
    GREATER_THAN_EQUAL = "greater_than_equal"


@dataclass
class RuleCondition:
    expected: RuleValue
    operator: OperatorEnum
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def evaluate_condition(self, actual: RuleValue | None) -> bool:
        if actual is None:
            return False

        if self.operator == OperatorEnum.EQUAL:
            return actual == self.expected

        if self.operator == OperatorEnum.NOT_EQUAL:
            return actual != self.expected

        try:
            parsed_actual = float(actual)
            parsed_expected = float(self.expected)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Numeric operators require actual and expected values to be numeric."
            ) from exc

        if self.operator == OperatorEnum.LESS_THAN:
            return parsed_actual < parsed_expected

        if self.operator == OperatorEnum.GREATER_THAN:
            return parsed_actual > parsed_expected

        if self.operator == OperatorEnum.LESS_THAN_EQUAL:
            return parsed_actual <= parsed_expected

        if self.operator == OperatorEnum.GREATER_THAN_EQUAL:
            return parsed_actual >= parsed_expected

        raise ValueError(f"Unsupported operator: {self.operator}")
