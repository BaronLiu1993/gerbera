from dataclasses import dataclass, field
import uuid

from gerbera_sdk.inference import Model
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.hardware.movement_system import MovementSystem

@dataclass
class HardwareSystem:
    name: str
    description: str = ""
    movement_systems: list[MovementSystem] = field(default_factory=list)
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    cameras: list[Camera] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def get_required_microcontroller_libraries(self) -> list[str]:
        libraries: list[str] = []
        normalized_library_names: set[str] = set()

        for microcontroller in self.microcontrollers:
            fqbn = microcontroller.fqbn
            if fqbn not in MICROCONTROLLER_MAPPING:
                raise ValueError(f"Unsupported microcontroller fqbn: {fqbn}")

            package_names = MICROCONTROLLER_MAPPING[fqbn]["libraries"]

            for library in package_names:
                normalized_library = library.strip().lower()
                if normalized_library not in normalized_library_names:
                    libraries.append(library)
                    normalized_library_names.add(normalized_library)
        return libraries
