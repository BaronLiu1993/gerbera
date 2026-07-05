from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from gerbera_sdk.classes.pin_factory import PinFactory


class ConnectionMode(str, Enum):
    READ = "read"
    WRITE = "write"
    BOTH = "both"


@dataclass
class Pin:
    """A single microcontroller pin and how the attached component uses it."""

    pin_val: str
    mode: ConnectionMode
    input_properties: Optional[dict[str, Any]] = None
    output_properties: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "pin": self.pin_val,
            "mode": self.mode.value,
        }

        payload.update(
            PinFactory.build(
                self.mode.value,
                input_properties=self.input_properties,
                output_properties=self.output_properties,
            )
        )
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Pin":
        input_schema = payload.get("inputSchema", {})
        output_schema = payload.get("outputSchema", {})

        return cls(
            pin_val=str(payload["pin"]),
            mode=ConnectionMode(payload["mode"]),
            input_properties=input_schema.get("properties", {}),
            output_properties=output_schema.get("properties", {}),
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
        return {
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "pins": [pin.to_dict() for pin in self.pins],
            "component_type": self.component_type,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            microcontroller_id=payload["microcontroller_id"],
            name=payload["name"],
            description=payload["description"],
            pins=[Pin.from_dict(pin) for pin in payload.get("pins", [])],
            component_type=payload["component_type"],
        )
