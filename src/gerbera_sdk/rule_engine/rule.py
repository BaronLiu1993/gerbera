from dataclasses import dataclass, field
import uuid

from gerbera_sdk.rule_engine.rule_callback import RuleCallback
from gerbera_sdk.rule_engine.rule_condition import RuleCondition


@dataclass
class Rule:
    condition: RuleCondition
    callback: RuleCallback
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
