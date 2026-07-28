from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.events.rules.rule_bus import RuleBus
from gerbera_sdk.events.rules.rule_condition import RuleValue
from gerbera_sdk.utils import EventKey, build_event_key


@dataclass
class RuleBuffer:
    rule_bus: RuleBus
    buffer: dict[EventKey, RuleValue | None] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def register_event_in_buffer(
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

        if event_key in self.buffer:
            return

        self.buffer[event_key] = None

    def unregister_event_from_buffer(
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
        self.buffer.pop(event_key, None)

    async def update_buffer_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, RuleValue],
    ) -> Any:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )

        if event_key not in self.buffer or len(payload) != 1:
            return

        value = next(iter(payload.values()))
        self.buffer[event_key] = value
        return await self.rule_bus.emit_evaluation_event(event_key, value)
