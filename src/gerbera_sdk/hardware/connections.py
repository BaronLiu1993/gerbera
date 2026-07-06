from dataclasses import dataclass
from typing import Any

from gerbera_sdk.components.registry import ComponentRegistry
from gerbera_sdk.hardware.pin_factory import PinFactory


@dataclass
class Connection:
    """A named hardware component attached to a microcontroller."""

    microcontroller_id: str
    name: str
    description: str
    pins: dict[str, str]
    component_type: str

    def to_dict(self) -> dict[str, Any]:
        ComponentRegistry.validate_pins(self.component_type, self.pins)
        payload = {
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "pins": dict(self.pins),
            "component_type": self.component_type,
        }
        payload.update(PinFactory.build(self.component_type))
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            microcontroller_id=payload["microcontroller_id"],
            name=payload["name"],
            description=payload["description"],
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            component_type=payload["component_type"],
        )
