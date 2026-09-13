from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.firmware.firmware_schema import ColumnType, PinMode


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

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "PinConfig":
        return cls(
            mode=PinMode(data["mode"]),
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
class DeviceConfig:
    component_type: str
    capabilities: CapabilityConfig
    libraries: tuple[LibraryConfig, ...]
    pins: dict[str, PinConfig]
    state: StateConfig
    commands: tuple[CommandConfig, ...]
    firmware: FirmwareConfig
    stream: StreamConfig

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "DeviceConfig":
        return cls(
            component_type=data["component_type"],
            capabilities=CapabilityConfig.from_data(data["capabilities"]),
            libraries=tuple(
                LibraryConfig.from_data(library_data)
                for library_data in data["libraries"]
            ),
            pins={
                name: PinConfig.from_data(pin_data)
                for name, pin_data in data["pins"].items()
            },
            state=StateConfig.from_data(data["state"]),
            commands=tuple(
                CommandConfig.from_data(command_data)
                for command_data in data["commands"]
            ),
            firmware=FirmwareConfig.from_data(data["firmware"]),
            stream=StreamConfig.from_data(data["stream"]),
        )
