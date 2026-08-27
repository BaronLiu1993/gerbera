from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Optional

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import LibrarySpec
from gerbera_sdk.models.hardware.connection import Connection


@dataclass
class Microcontroller:
    name: str
    port: str
    fqbn: str
    baud_rate: int = 115200
    description: Optional[str] = None
    connections: list[Connection] = field(default_factory=list)
    config_path: Path = Path("config.json")

    @property
    def id(self) -> str:
        return self.get_microcontroller_id_from_config()

    def get_microcontroller_id_from_config(self) -> str | None:

        if not self.config_path.exists():
            raise FileNotFoundError("Config.json Not Found")

        config = json.loads(self.config_path.read_text())

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
            builder = get_device_builder(connection.component_type)
            for library in builder.required_libraries():
                install_name = library.install.strip()
                normalized_install_name = install_name.lower()

                if normalized_install_name not in normalized_library_names:
                    libraries.append(library)
                    normalized_library_names.add(normalized_install_name)
        return libraries
