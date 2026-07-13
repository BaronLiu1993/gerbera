from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.models.database import Database
from gerbera_sdk.models.microcontroller import Microcontroller
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "microcontrollers": [
                microcontroller.to_dict()
                for microcontroller in self.microcontrollers
            ],
            "database": self.database.to_dict() if self.database is not None else None,
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
            database=(
                Database.from_dict(payload["database"])
                if payload.get("database") is not None
                else None
            ),
        )
    
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

        if self.database is not None and microcontroller.database is None:
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
