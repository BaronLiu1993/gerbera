from dataclasses import dataclass, field
from enum import Enum
import uuid

from gerbera_sdk.rule_engine.rule_event import RuleEvent


class Operator(Enum):
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_EQUAL = ">="
    LESS_THAN_EQUAL = "<="

@dataclass
class ConditionNode:
    field: str
    operator: Operator
    expected: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_events: list[RuleEvent] = field(default_factory=list)
    children: list["ConditionNode"] = field(default_factory=list)
