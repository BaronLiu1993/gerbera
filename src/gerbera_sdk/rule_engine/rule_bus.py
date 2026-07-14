from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.utils import EventKey, build_event_key
from gerbera_sdk.rule_engine.rule_group import RuleGroup


@dataclass
class RuleBus:
    rule_bus: dict[EventKey, list[RuleGroup]] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def register_rule_group(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        rule_group: RuleGroup,
    ) -> None:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        if event_key not in self.rule_bus:
            self.rule_bus[event_key] = []

        self.rule_bus[event_key].append(rule_group)
    
    def emit_evaluation_event(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> None:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )

        for rule_group in self.rule_bus.get(event_key, []):
            condition_res = rule_group.evaluate_rule_group()
            if condition_res:
                rule_group.callback()
