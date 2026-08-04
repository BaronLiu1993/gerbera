from dataclasses import dataclass, field
import uuid

from gerbera_sdk.inference import Model
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING
from gerbera_sdk.models.hardware.microcontroller import Microcontroller

@dataclass
class HardwareSystem:
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    cameras: list[Camera] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def _get_required_microcontroller_libraries(self) -> list[str]:
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

    def add_microcontrollers(self, microcontrollers: list[Microcontroller]) -> None:
        existing_ids = {microcontroller.id for microcontroller in self.microcontrollers}
        seen_ids: set[str] = set()

        for microcontroller in microcontrollers:
            if microcontroller.id in seen_ids:
                raise ValueError(f"Duplicate microcontroller in input: {microcontroller.id}")

            if microcontroller.id in existing_ids:
                raise ValueError(
                    f"Microcontroller already exists in hardware system {self.id}: "
                    f"{microcontroller.id}"
                )

            seen_ids.add(microcontroller.id)
            self.microcontrollers.append(microcontroller)

    def add_cameras(self, cameras: list[Camera]) -> None:
        existing_ids = {camera.id for camera in self.cameras}
        seen_ids: set[str] = set()

        for camera in cameras:
            if camera.id in seen_ids:
                raise ValueError(f"Duplicate camera in input: {camera.id}")

            if camera.id in existing_ids:
                raise ValueError(
                    f"Camera already exists in hardware system {self.id}: "
                    f"{camera.id}"
                )

            seen_ids.add(camera.id)
            self.cameras.append(camera)
