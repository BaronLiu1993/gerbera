from dataclasses import dataclass, field
from typing import Any, Callable
import uuid

from gerbera_sdk.rule_engine.rule_condition import RuleValue


@dataclass
class RuleCallback:
    callback: Callable[[RuleValue], Any]
    val: RuleValue | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def define(self, val: RuleValue) -> Any:
        return self.callback(val)

    def __call__(self, val: RuleValue) -> Any:
        self.val = val
        return self.define(val)
