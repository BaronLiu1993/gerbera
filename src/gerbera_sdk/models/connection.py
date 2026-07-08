from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Connection:
    id: str = ""
    microcontroller_id: str = ""
    name: str = ""
    component_type: str = ""
    pins: Optional[dict[str, str]] = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "component_type": self.component_type,
            "pins": dict(self.pins or {}),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            id=str(payload.get("id", "")),
            microcontroller_id=str(payload.get("microcontroller_id", "")),
            name=str(payload.get("name", "")),
            component_type=str(payload.get("component_type", "")),
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            description=str(payload.get("description", "")),
        )
