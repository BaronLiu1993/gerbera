from dataclasses import field
import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.dataclasses import dataclass
import yaml

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
    runtime_transport: RuntimeTransportConfig | None = None


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Microcontroller:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    port: Annotated[str, Field(min_length=1, pattern=r"\S")]
    fqbn: Annotated[str, Field(min_length=1, pattern=r"\S")]
    watchdog: RuntimeWatchdogConfig = field(default_factory=RuntimeWatchdogConfig)
    baud_rate: Annotated[int, Field(gt=0)] = 115200
    description: str | None = None
    connections: list[Connection] = field(default_factory=list)
    config_path: Path = Path(".gerbera/sdk/runtime.json")
    hardware_system_id: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None
    device_id: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None
    upload_port: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None
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
            transport_data = registered_device.runtime_transport
            if transport_data is not None:
                return transport_data
        return RuntimeTransportConfig.usb_serial(self.port)

    def get_microcontroller_id_from_config(self) -> str:
        registered_device = self.get_registered_device()
        if registered_device is None:
            raise ValueError(
                "No configured device matched port for upload: "
                f"{self.firmware_upload_port}"
            )
        return registered_device.id

    def get_registered_device(self) -> RegisteredDevice | None:
        if not self.config_path.exists():
            if self.device_id is not None:
                return None
            raise FileNotFoundError(
                f"Microcontroller configuration not found: {self.config_path}"
            )
        config = self.read_config()
        registry = config.get("devices")
        if not registry:
            if self.device_id is not None:
                return None
            raise ValueError("Devices are missing from project configuration")
        upload_port = self.firmware_upload_port
        devices = TypeAdapter(dict[str, RegisteredDevice]).validate_json(json.dumps(registry))
        for device in devices.values():
            if self.device_id is not None:
                if device.id == self.device_id:
                    return device
            elif device.address == upload_port:
                return device
        return None

    def read_config(self) -> dict[str, Any]:
        if self.config_path.suffix == ".json":
            config = json.loads(self.config_path.read_text())
        else:
            config = yaml.safe_load(self.config_path.read_text())
        if not isinstance(config, dict):
            raise ValueError(
                f"Microcontroller configuration must be a mapping: "
                f"{self.config_path}"
            )
        return config

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
