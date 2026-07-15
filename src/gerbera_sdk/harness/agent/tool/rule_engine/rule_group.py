from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable
from enum import Enum
import uuid

from gerbera_sdk.harness.agent.tool.rule_engine.condition import Condition

if TYPE_CHECKING:
    from gerbera_sdk.harness.agent.tool.rule_engine.rule_buffer import RuleBuffer


class RuleGroupOperatorEnum(Enum):
    AND = "and"
    OR = "or"

# Have user create a new instance of the object
@dataclass
class RuleGroup:
    conditions: list[Condition] # Has to be passed in to create the class
    operator: RuleGroupOperatorEnum
    callback: Callable[[], None]
    rule_buffer: "RuleBuffer | None" = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def _get_actual_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        field_name: str,
    ) -> str:
        if self.rule_buffer is None:
            raise RuntimeError("RuleGroup must be attached to a RuleBuffer before evaluation")

        actual = self.rule_buffer.read_event_value(
            event_type,
            microcontroller_id,
            event_name,
            field_name,
        )
        return str(actual)


    def evaluate_rule_group(self) -> bool:
        if self.operator == RuleGroupOperatorEnum.AND:
            for condition in self.conditions:
                actual = self._get_actual_value(
                    condition.event_type,
                    condition.microcontroller_id,
                    condition.event_name,
                    condition.field_name,
                )
                rule_check = condition.evaluate_condition(actual)

                if not rule_check:
                    return False
                
            return True

        elif self.operator == RuleGroupOperatorEnum.OR:
            for condition in self.conditions:
                actual = self._get_actual_value(
                    condition.event_type,
                    condition.microcontroller_id,
                    condition.event_name,
                    condition.field_name,
                )
                rule_check = condition.evaluate_condition(actual)

                if rule_check:
                    return True
            
            return False

        raise ValueError(f"Unsupported rule group operator: {self.operator}")
