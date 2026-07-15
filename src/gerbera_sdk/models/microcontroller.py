from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.contracts.firmware_contract import LibrarySpec
from gerbera_sdk.models.connection import Connection
from gerbera_sdk.models.database import Database

CONFIG_PATH = Path("config.json")


@dataclass
class Microcontroller:
    id: str = ""
    hardware_system_id: str = ""
    port: str = ""
    baud_rate: int = 115200
    fqbn: str = ""
    description: str = ""
    firmware_file_path: str = ""
    connections: list[Connection] = field(default_factory=list)
    database: Database | None = None
    _resolved_id_from_port: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        resolved_id = self._resolve_id_from_port()
        if not resolved_id:
            raise ValueError(
                "Microcontroller id must be resolved from config.json['devices'] via port; "
                "explicit ids are not allowed."
            )

        self.id = resolved_id
        self._resolved_id_from_port = True

        if not self.connections:
            return

        connections = list(self.connections)
        self.connections = []
        self.add_connections(connections)

    @property
    def microcontroller_id(self) -> str:
        return self.id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hardware_system_id": self.hardware_system_id,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "fqbn": self.fqbn,
            "description": self.description,
            "firmware_file_path": self.firmware_file_path,
            "connections": [connection.to_dict() for connection in self.connections],
            "database": self.database.to_dict() if self.database is not None else None,
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
            firmware_file_path=str(payload.get("firmware_file_path", "")),
            connections=[
                Connection.from_dict(connection)
                for connection in payload.get("connections", [])
            ],
            database=(
                Database.from_dict(payload["database"])
                if payload.get("database") is not None
                else None
            ),
        )

    def add_connections(
        self,
        connections: list[Connection],
    ) -> None:
        pending_connections = list(connections)
        connection_names = {connection.name for connection in self.connections}

        for connection in pending_connections:
            self._prepare_connection(connection)

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

    def _prepare_connection(self, connection: Connection) -> None:
        if not self.hardware_system_id:
            raise ValueError(
                f"Microcontroller {self.id} must belong to a hardware system "
                "before adding connections"
            )

        if not connection.hardware_system_id:
            connection.hardware_system_id = self.hardware_system_id

        if connection.hardware_system_id != self.hardware_system_id:
            raise ValueError(
                f"Connection {connection.name} belongs to hardware system "
                f"{connection.hardware_system_id}, expected {self.hardware_system_id}"
            )

        if not connection.microcontroller_id:
            connection.microcontroller_id = self.id

        if connection.microcontroller_id != self.id:
            if self._resolved_id_from_port:
                connection.microcontroller_id = self.id
            else:
                raise ValueError(
                    f"Connection {connection.name} belongs to microcontroller "
                    f"{connection.microcontroller_id}, expected {self.id}"
                )

        if (
            connection.database is None
            and self.database is not None
            and connection.component_type in DEVICES_MAPPING
        ):
            builder = DEVICES_MAPPING[connection.component_type]()
            if builder.supports_database:
                connection.database = self.database

    def get_required_libraries(self) -> list[LibrarySpec]:
        libraries: list[LibrarySpec] = []
        normalized_library_names: set[str] = set()

        for connection in self.connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for library resolution: "
                    f"{connection.component_type}"
                )

            builder = DEVICES_MAPPING[connection.component_type]()
            for library in builder.required_libraries():
                install_name = library.install.strip()
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in normalized_library_names:
                    continue

                libraries.append(library)
                normalized_library_names.add(normalized_install_name)

        return libraries

    def set_firmware_file(self, path) -> None:
        self.firmware_file_path = path

    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins.values():
                used_pins.add(pin)

        return used_pins

    def _resolve_id_from_port(self) -> str | None:
        if not self.port:
            raise ValueError("Microcontroller port is required for config lookup")

        if not CONFIG_PATH.exists():
            raise FileNotFoundError("config.json not found")

        config = json.loads(CONFIG_PATH.read_text())
        registry = config.get("devices", {})
        if not isinstance(registry, dict):
            raise ValueError("config.json['devices'] must be an object")

        for device_id, device in registry.items():
            device_port = str(device.get("address")).strip()

            if device_port != self.port:
                continue

            resolved_id = str(device.get("id", "")).strip()
            if resolved_id:
                return resolved_id

            fallback_id = str(device_id).strip()
            return fallback_id or None

        raise ValueError(
            f"No device in config.json['devices'] matched port {self.port!r}"
        )
