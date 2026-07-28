from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.rules.rule import Rule
from gerbera_sdk.utils import EventKey, build_event_key


@dataclass
class RuleBus:
    rule_bus: dict[EventKey, Rule] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def register_rule(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        rule: Rule,
    ) -> None:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )

        if event_key in self.rule_bus:
            raise ValueError(f"Rule already registered for event: {event_key}")

        self.rule_bus[event_key] = rule

    def get_rule(self, event_key: EventKey) -> Rule | None:
        return self.rule_bus.get(event_key)

    def unregister_rule(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> Rule:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        try:
            return self.rule_bus.pop(event_key)
        except KeyError as exc:
            raise ValueError(
                f"Rule is not registered for event: {event_key}"
            ) from exc

    async def emit_evaluation_event(
        self,
        event_key: EventKey,
        actual: float,
    ) -> object | None:
        rule = self.get_rule(event_key)
        if rule is None:
            return

        if not rule.condition.evaluate_condition(actual):
            return

        return await rule.callback(val=actual)
