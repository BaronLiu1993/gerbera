from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.firmware.firmware_schema import ColumnType, PinMode


@dataclass(frozen=True)
class CapabilityConfig:
    streaming: bool = False

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "CapabilityConfig":
        data = data or {}
        return cls(streaming=bool(data.get("streaming", False)))


@dataclass(frozen=True)
class LibraryConfig:
    include: str
    install: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "LibraryConfig":
        return cls(include=str(data["include"]), install=str(data["install"]))


@dataclass(frozen=True)
class ParameterConfig:
    required: bool = True
    description: str = ""
    min: int | float | None = None
    max: int | float | None = None

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "ParameterConfig":
        data = data or {}
        return cls(
            required=bool(data.get("required", True)),
            description=str(data.get("description", "")),
            min=data.get("min"),
            max=data.get("max"),
        )


@dataclass(frozen=True)
class AnnotationConfig:
    title: str
    read_only_hint: bool
    open_world_hint: bool

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "AnnotationConfig":
        return cls(
            title=str(data["title"]),
            read_only_hint=bool(data["readOnlyHint"]),
            open_world_hint=bool(data["openWorldHint"]),
        )


@dataclass(frozen=True)
class CommandConfig:
    method: str
    description: str
    params: dict[str, ParameterConfig] = field(default_factory=dict)
    annotations: AnnotationConfig | None = None
    enabled_when: str = "always"

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "CommandConfig":
        params = {
            name: ParameterConfig.from_data(param_data)
            for name, param_data in (data.get("params") or {}).items()
        }
        annotation_data = data.get("annotations")
        return cls(
            method=str(data["method"]),
            description=str(data.get("description", "")),
            params=params,
            annotations=(
                AnnotationConfig.from_data(annotation_data)
                if annotation_data
                else None
            ),
            enabled_when=str(data.get("enabled_when", "always")),
        )


@dataclass(frozen=True)
class StateConfig:
    units: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "StateConfig":
        data = data or {}
        return cls(units=dict(data.get("units") or {}))


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
            type=ColumnType(str(data["type"])),
            idx=bool(data.get("idx", False)),
            primary_key=bool(data.get("primary_key", False)),
            nullable=bool(data.get("nullable", True)),
            default=data.get("default"),
            sql_suffix=data.get("sql_suffix"),
        )


@dataclass(frozen=True)
class StreamConfig:
    schema: dict[str, ColumnConfig] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "StreamConfig":
        data = data or {}
        return cls(
            schema={
                name: ColumnConfig.from_data(column_data)
                for name, column_data in (data.get("schema") or {}).items()
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
    def from_data(cls, data: dict[str, Any] | None) -> "FirmwareConfig":
        data = data or {}
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
    pins: dict[str, PinMode]
    state: StateConfig
    commands: tuple[CommandConfig, ...]
    firmware: FirmwareConfig
    stream: StreamConfig

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "DeviceConfig":
        return cls(
            component_type=str(data["component_type"]),
            capabilities=CapabilityConfig.from_data(data.get("capabilities")),
            libraries=tuple(
                LibraryConfig.from_data(library_data)
                for library_data in data.get("libraries", [])
            ),
            pins={
                name: PinMode(str(mode))
                for name, mode in (data.get("pins") or {}).items()
            },
            state=StateConfig.from_data(data.get("state")),
            commands=tuple(
                CommandConfig.from_data(command_data)
                for command_data in data.get("commands", [])
            ),
            firmware=FirmwareConfig.from_data(data.get("firmware")),
            stream=StreamConfig.from_data(data.get("stream")),
        )
