from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.firmware.function.configurations import BUILDER_MAPPING
from gerbera_sdk.models.connection import Connection


@dataclass
class Microcontroller:
    id: str
    hardware_system_id: str
    port: str
    baud_rate: int
    fqbn: str
    description: str = ""
    firmware_file_path: str = ""
    connections: list[Connection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hardware_system_id": self.hardware_system_id,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "fqbn": self.fqbn,
            "description": self.description,
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Microcontroller":
        return cls(
            id=str(payload["id"]),
            hardware_system_id=str(payload["hardware_system_id"]),
            port=str(payload["port"]),
            baud_rate=int(payload.get("baud_rate")),
            fqbn=str(payload.get("fqbn")),
            description=str(payload.get("description", "")),
            connections=[
                Connection.from_dict(connection)
                for connection in payload.get("connections", [])
            ],
        )

    def add_connections(
        self,
        connections: list[Connection],
    ) -> None:
        pending_connections = list(connections)
        connection_names = {connection.name for connection in self.connections}

        for connection in pending_connections:
            if connection.name in connection_names:
                raise ValueError(
                    f"Connection name already exists on board {self.id}: "
                    f"{connection.name}"
                )

            used_pins = self._get_used_pins()
            for pin in connection.pins.values():
                if pin in used_pins:
                    raise ValueError(
                        f"Pin already in use on board {self.id}: {pin}"
                    )

            self.connections.append(connection)

    def get_required_libraries(self) -> list[str]:
        libraries: list[str] = []

        for connection in self.connections:
            if connection.component_type not in BUILDER_MAPPING:
                raise ValueError(
                    f"Unsupported component type for library resolution: "
                    f"{connection.component_type}"
                )

            builder = BUILDER_MAPPING[connection.component_type]()
            for library in builder.required_libraries():
                if library not in libraries:
                    libraries.append(library)

        return libraries
    
    def set_firmware_file(self, path) -> None:
        self.firmware_file_path = path

    # Helper Functions for Deduping
    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins.values():
                used_pins.add(pin)

        return used_pins
