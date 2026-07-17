from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING


@dataclass
class HardwareSystem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)

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
