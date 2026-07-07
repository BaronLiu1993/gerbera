from dataclasses import dataclass
from typing import Any


@dataclass
class Connection:
    id: str = ""
    microcontroller_id: str = ""
    name: str = ""
    description: str = ""
    pins: dict[str, str] = None
    component_type: str = ""
    pins: dict = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "pins": dict(self.pins),
            "component_type": self.component_type,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            id=str(payload.get("id", "")),
            microcontroller_id=str(payload.get("microcontroller_id", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            component_type=str(payload.get("component_type", "")),
        )
