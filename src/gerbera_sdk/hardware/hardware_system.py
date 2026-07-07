from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.hardware.microcontroller import Microcontroller


@dataclass
class HardwareSystem:
    id: str
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "microcontrollers": [
                microcontroller.to_dict()
                for microcontroller in self.microcontrollers
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HardwareSystem":
        return cls(
            id=str(payload["id"]),
            description=str(payload.get("description", "")),
            microcontrollers=[
                Microcontroller.from_dict(microcontroller)
                for microcontroller in payload.get("microcontrollers", [])
            ],
        )
    
    # Add All Microcontrollers at Once to The List
    def add_microcontrollers(self, microcontrollers: list[Microcontroller]) -> None:
        existing_microcontroller_ids = {
            microcontroller.id for microcontroller in self.microcontrollers
        }

        for microcontroller in microcontrollers:
            if microcontroller.id in existing_microcontroller_ids:
                raise ValueError(
                    f"Microcontroller already exists in hardware system {self.id}: "
                    f"{microcontroller.id}"
                )

            existing_microcontroller_ids.add(microcontroller.id)
            self.microcontrollers.append(microcontroller)

    
