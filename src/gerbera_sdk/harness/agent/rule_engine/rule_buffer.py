from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.utils import EventKey
from gerbera_sdk.harness.agent.rule_engine.rule_bus import RuleBus



@dataclass
class RuleBuffer:
    rule_bus: "RuleBus"
    buffer: dict[EventKey, dict[str, Any]] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def register_event_in_buffer(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        schema: dict[str, Any] | None = None,
    ) -> None:
        event_key = self._build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )

        if event_key in self.buffer:
            return

        event_payload: dict[str, Any] = {}
        for field_name in (schema or {}).keys():
            event_payload[str(field_name)] = None

        self.buffer[event_key] = event_payload

    def update_event_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        event_key = self._build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        event_payload = self._get_event_payload(event_key)

        for key, value in payload.items():
            event_payload[str(key)] = value

        self.rule_bus.emit_evaluation_event(
            event_type,
            microcontroller_id,
            event_name,
        )

    def read_event_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        field_name: str,
    ) -> Any:
        event_key = self._build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        event_payload = self._get_event_payload(event_key)

        if field_name not in event_payload:
            raise KeyError(
                f"Field is not registered in rule buffer for {event_key}: "
                f"{field_name}"
            )

        return event_payload[field_name]

    def read_event_payload(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> dict[str, Any]:
        event_key = self._build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        return dict(self._get_event_payload(event_key))

    def _get_event_payload(self, event_key: EventKey) -> dict[str, Any]:
        if event_key not in self.buffer:
            raise KeyError(f"Event is not registered in rule buffer: {event_key}")

        return self.buffer[event_key]

    def _build_event_key(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> EventKey:
        return (
            str(event_type),
            str(microcontroller_id),
            str(event_name),
        )
