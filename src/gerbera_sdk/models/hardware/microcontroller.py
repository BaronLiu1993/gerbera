from dataclasses import dataclass, field

from gerbera_sdk.firmware.devices.config_schema import LibraryConfig
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.firmware.firmware_schema import BoardTransportKind
from gerbera_sdk.models.hardware.connection import Connection


@dataclass(frozen=True)
class RuntimeTransportConfig:
    kind: BoardTransportKind
    port: str
    device_name: str | None = None

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
    device_id: str
    upload_port: str
    fqbn: str
    runtime_transport: RuntimeTransportConfig
    baud_rate: int = 115200
    description: str | None = None
    connections: list[Connection] = field(default_factory=list)
    hardware_system_id: str | None = None

    @property
    def id(self) -> str:
        return self.device_id

    def get_required_connection_libraries(self) -> list[LibraryConfig]:
        libraries_by_name: dict[str, LibraryConfig] = {}

        for connection in self.connections:
            builder = get_device_builder(connection.component_type)
            for library in builder.required_libraries():
                install_name = library.install.strip().lower()
                libraries_by_name.setdefault(install_name, library)

        return list(libraries_by_name.values())
