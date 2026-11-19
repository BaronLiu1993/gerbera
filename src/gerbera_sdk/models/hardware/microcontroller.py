from dataclasses import field
from typing import Annotated

from pydantic import ConfigDict, Field, model_validator
from pydantic.dataclasses import dataclass

from gerbera_sdk.firmware.devices.config_schema import LibraryConfig
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.firmware.firmware_schema import BoardTransportKind
from gerbera_sdk.models.hardware.connection import Connection


NonBlankString = Annotated[str, Field(min_length=1, pattern=r"\S")]


@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class RuntimeTransportConfig:
    kind: BoardTransportKind
    port: NonBlankString
    device_name: NonBlankString | None = None

    @model_validator(mode="after")
    def validate_device_name(self) -> "RuntimeTransportConfig":
        if self.kind == BoardTransportKind.BLUETOOTH_CLASSIC and self.device_name is None:
            raise ValueError("Bluetooth transport requires device_name")
        return self

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


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Microcontroller:
    name: NonBlankString
    device_id: NonBlankString
    upload_port: NonBlankString
    fqbn: NonBlankString
    runtime_transport: RuntimeTransportConfig
    baud_rate: Annotated[int, Field(gt=0)] = 115200
    description: str | None = None
    connections: list[Connection] = field(default_factory=list)
    hardware_system_id: NonBlankString | None = None

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
