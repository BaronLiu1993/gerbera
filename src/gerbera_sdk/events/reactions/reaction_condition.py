from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated
import uuid


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
