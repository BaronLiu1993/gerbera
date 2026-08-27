from dataclasses import asdict, dataclass
from typing import Any

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class MovementRuntime:
    hardware_system: HardwareSystem

    def get_movement_system(self) -> dict[str, Any]:
        if self.hardware_system.movement_system is None:
            raise ValueError("Cannot get movement system as it is not initialised")
        return asdict(self.hardware_system.movement_system)