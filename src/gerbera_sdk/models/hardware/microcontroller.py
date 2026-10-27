from dataclasses import field
import json
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.dataclasses import dataclass

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import (
    BoardTransportKind,
    LibrarySpec,
)
from gerbera_sdk.models.hardware.connection import Connection


@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class RuntimeWatchdogConfig:
    heartbeat_interval_ms: Annotated[int, Field(gt=0)] = 500
    heartbeat_timeout_ms: Annotated[int, Field(gt=0)] = 2500


@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class RuntimeTransportConfig:
    kind: BoardTransportKind
    port: Annotated[str, Field(min_length=1, pattern=r"\S")]
    device_name: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None

    @classmethod
    def from_data(
        cls,
        data: dict[str, Any],
    ) -> "RuntimeTransportConfig":
        return TypeAdapter(cls).validate_json(json.dumps(data))

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


class RegisteredDevice(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", validate_default=True)

    id: str = Field(min_length=1, pattern=r"\S")
    address: str = Field(min_length=1, pattern=r"\S")
    protocol: str = Field(min_length=1, pattern=r"\S")
    fqbn: str = Field(min_length=1, pattern=r"\S")


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Microcontroller:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    device_id: Annotated[str, Field(min_length=1, pattern=r"\S")]
    upload_port: Annotated[str, Field(min_length=1, pattern=r"\S")]
    fqbn: Annotated[str, Field(min_length=1, pattern=r"\S")]
    runtime_transport: RuntimeTransportConfig
    watchdog: RuntimeWatchdogConfig = field(default_factory=RuntimeWatchdogConfig)
    baud_rate: Annotated[int, Field(gt=0)] = 115200
    description: str | None = None
    connections: list[Connection] = field(default_factory=list)
    hardware_system_id: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None

    @property
    def id(self) -> str:
        return self.device_id

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
