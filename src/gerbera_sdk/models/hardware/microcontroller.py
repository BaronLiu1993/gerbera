from dataclasses import dataclass, field
import json
from pathlib import Path
\
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.contracts.firmware_contract import LibrarySpec
from gerbera_sdk.models.hardware.connection import Connection

CONFIG_PATH = Path("config.json")

@dataclass
class Microcontroller:
    port: str
    baud_rate: int = 115200
    fqbn: str
    description: str = ""
    connections: list[Connection] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self._get_microcontroller_id_from_config()

    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins.values():
                used_pins.add(pin)

        return used_pins

    def _get_microcontroller_id_from_config(self) -> str | None:

        if not CONFIG_PATH.exists():
            raise FileNotFoundError("Config.json Not Found")

        config = json.loads(CONFIG_PATH.read_text())

        registry = config.get("devices")

        if not registry:
            raise ValueError("Devices is Not Found in Config.json")

        for device in registry.values():
            device_port = device.get("address")
            if device_port == self.port:
                return device.get("id")

        raise ValueError(
            f"No device in config.json['devices'] matched port {self.port}"
        )

    
    def _get_required_connection_libraries(self) -> list[LibrarySpec]:
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

                if normalized_install_name not in normalized_library_names:
                    libraries.append(library)
                    normalized_library_names.add(normalized_install_name)
        return libraries

    def add_connections(
        self,
        connections: list[Connection],
    ) -> None:
        connection_names = {connection.name for connection in self.connections}

        for connection in connections:
            if connection.name in connection_names:
                raise ValueError(
                    f"Connection name already exists on board {self.id}: "
                    f"{connection.name}"
                )

            used_pins = self._get_used_pins()
            for pin in connection.pins.values():
                if pin in used_pins:
                    raise ValueError(f"Pin already in use on board {self.id}: {pin}")
                
            connection.microcontroller_id = self.id
            self.connections.append(connection)
