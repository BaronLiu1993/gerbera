from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from gerbera_sdk.firmware.firmware_schema import (
    ColumnType,
    PinAssignmentMode,
    PinCapability,
    PinMode,
)


def validate_config_fields(
    data: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> None:
    allowed = required | (optional or set())
    missing_fields = required - data.keys()
    unknown_fields = data.keys() - allowed
    if missing_fields:
        raise ValueError(
            f"{label} is missing required field(s): "
            f"{', '.join(sorted(missing_fields))}"
        )
    if unknown_fields:
        raise ValueError(
            f"{label} contains unknown field(s): "
            f"{', '.join(sorted(unknown_fields))}"
        )


@dataclass(frozen=True)
class CapabilityConfig:
    streaming: bool

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "CapabilityConfig":
        return cls(streaming=data["streaming"])


@dataclass(frozen=True)
class LibraryConfig:
    include: str
    install: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "LibraryConfig":
        return cls(include=data["include"], install=data["install"])


@dataclass(frozen=True)
class ParameterConfig:
    required: bool
    description: str
    min: int | float | None = None
    max: int | float | None = None

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ParameterConfig":
        return cls(
            required=data["required"],
            description=data["description"],
            min=data["min"],
            max=data["max"],
        )


@dataclass(frozen=True)
class AnnotationConfig:
    title: str
    read_only_hint: bool
    open_world_hint: bool

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "AnnotationConfig":
        return cls(
            title=data["title"],
            read_only_hint=data["readOnlyHint"],
            open_world_hint=data["openWorldHint"],
        )


@dataclass(frozen=True)
class CommandConfig:
    method: str
    description: str
    params: dict[str, ParameterConfig]
    annotations: AnnotationConfig
    enabled_when: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "CommandConfig":
        params = {
            name: ParameterConfig.from_data(param_data)
            for name, param_data in data["params"].items()
        }
        return cls(
            method=data["method"],
            description=data["description"],
            params=params,
            annotations=AnnotationConfig.from_data(data["annotations"]),
            enabled_when=data["enabled_when"],
        )


@dataclass(frozen=True)
class StateConfig:
    units: dict[str, str | None]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "StateConfig":
        return cls(units=data["units"])


@dataclass(frozen=True)
class PinConfig:
    mode: PinMode
    capabilities: frozenset[PinCapability]
    assignment: PinAssignmentMode

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "PinConfig":
        required_fields = {"mode", "capabilities", "assignment"}
        validate_config_fields(
            data,
            required=required_fields,
            label="Pin configuration",
        )

        capability_values = data["capabilities"]
        if not isinstance(capability_values, list):
            raise ValueError("Pin capabilities must be a list")

        capabilities = frozenset(
            PinCapability(capability) for capability in capability_values
        )
        if not capabilities:
            raise ValueError(
                "Pin configuration must require at least one capability"
            )

        return cls(
            mode=PinMode(data["mode"]),
            capabilities=capabilities,
            assignment=PinAssignmentMode(data["assignment"]),
        )


@dataclass(frozen=True)
class ColumnConfig:
    type: ColumnType
    idx: bool = False
    primary_key: bool = False
    nullable: bool = True
    default: str | None = None
    sql_suffix: str | None = None

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ColumnConfig":
        return cls(
            type=ColumnType(data["type"]),
            idx=bool(data.get("idx", False)),
            primary_key=bool(data.get("primary_key", False)),
            nullable=bool(data.get("nullable", True)),
            default=data.get("default"),
            sql_suffix=data.get("sql_suffix"),
        )


@dataclass(frozen=True)
class StreamConfig:
    schema: dict[str, ColumnConfig]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "StreamConfig":
        return cls(
            schema={
                name: ColumnConfig.from_data(column_data)
                for name, column_data in data["schema"].items()
            }
        )


@dataclass(frozen=True)
class FirmwareConfig:
    definitions: str = ""
    definitions_when_streaming: str = ""
    setup: tuple[str, ...] = ()
    setup_when_streaming: tuple[str, ...] = ()
    stream_loop_when_streaming: str = ""
    handlers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "FirmwareConfig":
        return cls(
            definitions=str(data.get("definitions") or ""),
            definitions_when_streaming=str(
                data.get("definitions_when_streaming") or ""
            ),
            setup=tuple(data.get("setup") or ()),
            setup_when_streaming=tuple(data.get("setup_when_streaming") or ()),
            stream_loop_when_streaming=str(
                data.get("stream_loop_when_streaming") or ""
            ),
            handlers=dict(data.get("handlers") or {}),
        )


@dataclass(frozen=True)
class VerificationConfig:
    startup_timeout_ms: int
    monitor_interval_ms: int
    check: str
    monitor: str
    safe_stop: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "VerificationConfig":
        validate_config_fields(
            data,
            required={
                "startup_timeout_ms",
                "monitor_interval_ms",
                "check",
                "monitor",
                "safe_stop",
            },
            label="Verification configuration",
        )
        return cls(
            startup_timeout_ms=data["startup_timeout_ms"],
            monitor_interval_ms=data["monitor_interval_ms"],
            check=str(data["check"] or ""),
            monitor=str(data["monitor"] or ""),
            safe_stop=str(data["safe_stop"] or ""),
        )


@dataclass(frozen=True)
class DeviceConfig:
    component_type: str
    capabilities: CapabilityConfig
    libraries: tuple[LibraryConfig, ...]
    pins: Mapping[str, PinConfig]
    state: StateConfig
    commands: tuple[CommandConfig, ...]
    firmware: FirmwareConfig
    verification: VerificationConfig
    stream: StreamConfig

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "DeviceConfig":
        required_fields = {
            "component_type",
            "capabilities",
            "libraries",
            "pins",
            "state",
            "commands",
            "firmware",
            "verification",
            "stream",
        }
        validate_config_fields(
            data,
            required=required_fields,
            label="Device configuration",
        )
        component_type = data["component_type"]
        if not isinstance(component_type, str) or not component_type:
            raise ValueError(
                "Device configuration component_type must be a non-empty string"
            )
        pins_data = data["pins"]
        if not isinstance(pins_data, dict):
            raise ValueError("Device configuration pins must be a mapping")
        for pin_name in pins_data:
            if not isinstance(pin_name, str) or not pin_name:
                raise ValueError(
                    "Device configuration pin names must be non-empty strings"
                )

        return cls(
            component_type=component_type,
            capabilities=CapabilityConfig.from_data(data["capabilities"]),
            libraries=tuple(
                LibraryConfig.from_data(library_data)
                for library_data in data["libraries"]
            ),
            pins=MappingProxyType(
                {
                    name: PinConfig.from_data(pin_data)
                    for name, pin_data in pins_data.items()
                }
            ),
            state=StateConfig.from_data(data["state"]),
            commands=tuple(
                CommandConfig.from_data(command_data)
                for command_data in data["commands"]
            ),
            firmware=FirmwareConfig.from_data(data["firmware"]),
            verification=VerificationConfig.from_data(data["verification"]),
            stream=StreamConfig.from_data(data["stream"]),
        )
