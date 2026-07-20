from dataclasses import dataclass, field
from enum import Enum
import uuid

from gerbera_sdk.utils import EventKey


class OperatorEnum(Enum):
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_EQUAL = "<="
    GREATER_THAN_EQUAL = ">="


@dataclass
class Condition:
    event_type: str
    microcontroller_id: str
    event_name: str
    field_name: str
    expected: str
    operator: OperatorEnum
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def event_key(self) -> EventKey:
        return (
            self.event_type,
            self.microcontroller_id,
            self.event_name,
        )

    def evaluate_condition(self, actual: str) -> bool:
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
