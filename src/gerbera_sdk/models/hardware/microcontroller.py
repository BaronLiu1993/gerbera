from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Optional

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import (
    BoardTransportKind,
    LibrarySpec,
)
from gerbera_sdk.models.hardware.connection import Connection


@dataclass(frozen=True)
class RuntimeWatchdogConfig:
    heartbeat_interval_ms: int
    heartbeat_timeout_ms: int


@dataclass(frozen=True)
class RuntimeTransportConfig:
    kind: BoardTransportKind
    port: str
    device_name: str | None = None

    @classmethod
    def from_data(
        cls,
        data: dict[str, Any],
    ) -> "RuntimeTransportConfig":
        return cls(
            kind=BoardTransportKind(data["kind"]),
            port=data["port"],
            device_name=data.get("device_name"),
        )

    @classmethod
    def usb_serial(cls, port: str) -> "RuntimeTransportConfig":
        return cls(kind=BoardTransportKind.USB_SERIAL, port=port)

    @classmethod
    def bluetooth_classic(
        cls,
        port: str,
        device_name: str,
    ) -> "RuntimeTransportConfig":
        return cls(
            kind=BoardTransportKind.BLUETOOTH_CLASSIC,
            port=port,
            device_name=device_name,
        )


@dataclass
class Microcontroller:
    name: str
    port: str
    fqbn: str
    watchdog: RuntimeWatchdogConfig
    baud_rate: int = 115200
    description: Optional[str] = None
    connections: list[Connection] = field(default_factory=list)
    config_path: Path = Path("config.json")
    hardware_system_id: str | None = None
    device_id: str | None = None
    upload_port: str | None = None
    runtime_transport: RuntimeTransportConfig | None = None

    @property
    def id(self) -> str:
        if self.device_id is not None:
            return self.device_id
        return self.get_microcontroller_id_from_config()

    @property
    def firmware_upload_port(self) -> str:
        return self.upload_port or self.port

    @property
    def active_runtime_transport(self) -> RuntimeTransportConfig:
        if self.runtime_transport is not None:
            return self.runtime_transport
        registered_device = self.get_registered_device()
        if registered_device is not None:
            transport_data = registered_device.get("runtime_transport")
            if transport_data is not None:
                return RuntimeTransportConfig.from_data(transport_data)
        return RuntimeTransportConfig.usb_serial(self.port)

    def get_microcontroller_id_from_config(self) -> str:
        registered_device = self.get_registered_device()
        if registered_device is None:
            raise ValueError(
                "No device in config.json['devices'] matched port for upload: "
                f"{self.firmware_upload_port}"
            )
        device_id = registered_device.get("id")
        if not device_id:
            raise ValueError("Microcontroller id is missing from config.json")
        return device_id

    def get_registered_device(self) -> dict[str, Any] | None:
        if not self.config_path.exists():
            if self.device_id is not None:
                return None
            raise FileNotFoundError("Config.json Not Found")
        config = json.loads(self.config_path.read_text())
        registry = config.get("devices")
        if not registry:
            if self.device_id is not None:
                return None
            raise ValueError("Devices is Not Found in Config.json")
        upload_port = self.firmware_upload_port
        for device in registry.values():
            if self.device_id is not None and device.get("id") == self.device_id:
                return device
            if device.get("address") == upload_port:
                return device
        return None

    def get_required_connection_libraries(self) -> list[LibrarySpec]:
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
