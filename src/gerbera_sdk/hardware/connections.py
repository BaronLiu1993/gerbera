from dataclasses import dataclass
from typing import Any, List

from gerbera_sdk.hardware.pin_factory import PinFactory


@dataclass
class Pin:
    """A single microcontroller pin used by a component."""

    pin_val: str

    def to_dict(self) -> dict[str, Any]:
        return {"pin": self.pin_val}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Pin":
        return cls(
            pin_val=str(payload["pin"]),
        )


@dataclass
class Connection:
    """A named hardware component attached to a microcontroller."""

    microcontroller_id: str
    name: str
    description: str
    pins: List[Pin]
    component_type: str

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "pins": [pin.to_dict() for pin in self.pins],
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
            pins=[Pin.from_dict(pin) for pin in payload.get("pins", [])],
            component_type=payload["component_type"],
        )
