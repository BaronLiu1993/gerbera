from dataclasses import dataclass, field
from typing import Callable, Any
from condition import Condition
from enum import Enum
import uuid

from rule_buffer import RuleBuffer


class RuleGroupOperatorEnum(Enum):
    AND = "and"
    OR = "or"

@dataclass
class RuleGroup:
    conditions: list[Condition] # Has to be passed in to create the class
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operator: RuleGroupOperatorEnum
    callback: Callable[[dict[str, Any]], None]
    rule_buffer: RuleBuffer

    def _get_actual_value(self, event_type, microcontroller_id, event_name):
        event_key = (event_type, microcontroller_id, event_name)
        actual = self.rule_buffer.buffer[event_key]
        return actual


    def evaluate_rule_group(self) -> bool:
        if self.operator == RuleGroupOperatorEnum.AND:
            for condition in self.conditions:
                actual = self._get_actual_value(condition.event_type, condition.microcontroller_id, condition.event_name)
                rule_check = condition.evaluate_condition(actual)

                if not rule_check:
                    return False
                
            return True

        elif self.operator == RuleGroupOperatorEnum.OR:
            for condition in self.conditions:
                actual = self._get_actual_value(condition.event_type, condition.microcontroller_id, condition.event_name)
                rule_check = condition.evaluate_condition(actual)

                if rule_check:
                    return True
            
            return False
        
                

