from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated
import uuid

from pydantic import Field, StrictFloat, TypeAdapter, ValidationError


_REACTION_FLOAT_ADAPTER = TypeAdapter(
    Annotated[StrictFloat, Field(allow_inf_nan=False)]
)


def parse_reaction_value(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Reaction values must be finite numbers")

    try:
        normalized_value = float(value)
        return _REACTION_FLOAT_ADAPTER.validate_python(normalized_value)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("Reaction values must be finite numbers") from exc


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
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        self.expected = parse_reaction_value(self.expected)

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
