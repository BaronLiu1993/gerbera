from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.models.database import Database
from gerbera_sdk.models.microcontroller import Microcontroller
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING


@dataclass
class HardwareSystem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    database: Database | None = None

    def __post_init__(self) -> None:
        if self.database is not None and not self.database.hardware_system_id:
            self.database.hardware_system_id = self.id

        if self.microcontrollers:
            microcontrollers = list(self.microcontrollers)
            self.microcontrollers = []
            self.add_microcontrollers(microcontrollers)

    # Add All Microcontrollers at Once to The List
    def add_microcontrollers(self, microcontrollers: list[Microcontroller]) -> None:
        existing_microcontroller_ids = {
            microcontroller.id for microcontroller in self.microcontrollers
        }

        for microcontroller in microcontrollers:
            self._prepare_microcontroller(microcontroller)

            if microcontroller.id in existing_microcontroller_ids:
                raise ValueError(
                    f"Microcontroller already exists in hardware system {self.id}: "
                    f"{microcontroller.id}"
                )

            existing_microcontroller_ids.add(microcontroller.id)
            self.microcontrollers.append(microcontroller)

    def _prepare_microcontroller(self, microcontroller: Microcontroller) -> None:
        if not microcontroller.hardware_system_id:
            microcontroller.hardware_system_id = self.id

        if microcontroller.hardware_system_id != self.id:
            raise ValueError(
                f"Microcontroller {microcontroller.id} belongs to hardware system "
                f"{microcontroller.hardware_system_id}, expected {self.id}"
            )

        if microcontroller.database is None and self.database is not None:
            supports_database = any(
                connection.component_type in DEVICES_MAPPING
                and DEVICES_MAPPING[connection.component_type]().supports_database
                for connection in microcontroller.connections
            )
            if supports_database:
                microcontroller.database = self.database

        if microcontroller.connections:
            connections = list(microcontroller.connections)
            microcontroller.connections = []
            microcontroller.add_connections(connections)
    
    def get_required_microcontroller_packages(self) -> list[str]:
        libraries: list[str] = []
        normalized_library_names: set[str] = set()

        for microcontroller in self.microcontrollers:
            fqbn = microcontroller.fqbn
            if fqbn not in MICROCONTROLLER_MAPPING:
                raise ValueError(f"Unsupported microcontroller fqbn: {fqbn}")

            package_names = MICROCONTROLLER_MAPPING[fqbn]["libraries"]

            for library in package_names:
                normalized_library = library.strip().lower()
                if normalized_library in normalized_library_names:
                    continue

                libraries.append(library)
                normalized_library_names.add(normalized_library)

        return libraries
