from collections.abc import Mapping
import json
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import ConfigDict, Field, TypeAdapter, model_validator
from pydantic.dataclasses import dataclass

from gerbera_sdk.firmware.firmware_schema import (
    ColumnType,
    PinAssignmentMode,
    PinCapability,
    PinMode,
)
from gerbera_sdk.firmware.parameter_schema import ParameterDomain

DEVICE_SCHEMA_CONFIG = ConfigDict(strict=True, extra="forbid", validate_default=True)


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class CapabilityConfig:
    streaming: bool


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class LibraryConfig:
    include: str
    install: str


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class ParameterConfig:
    required: bool
    description: str
    domain: ParameterDomain


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class AnnotationConfig:
    title: str
    read_only_hint: bool
    open_world_hint: bool


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class CommandConfig:
    method: str
    description: str
    params: dict[str, ParameterConfig]
    annotations: AnnotationConfig
    enabled_when: str
    response_fields: Annotated[tuple[str, ...], Field(min_length=1)]


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class StateFieldConfig:
    unit: str | None
    domain: ParameterDomain


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class StateConfig:
    fields: Mapping[str, StateFieldConfig]

    def __post_init__(self):
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class PinConfig:
    mode: PinMode
    capabilities: Annotated[frozenset[PinCapability], Field(min_length=1)]
    assignment: PinAssignmentMode


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class ColumnConfig:
    type: ColumnType
    idx: bool
    primary_key: bool
    nullable: bool
    default: str | None
    sql_suffix: str | None


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class StreamConfig:
    schema: dict[str, ColumnConfig]
    payload_fields: tuple[str, ...]


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class FirmwareConfig:
    definitions: str
    definitions_when_streaming: str
    setup: tuple[str, ...]
    setup_when_streaming: tuple[str, ...]
    stream_loop_when_streaming: str
    handlers: dict[str, str]


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class VerificationConfig:
    startup_timeout_ms: int
    monitor_interval_ms: int
    check: str
    monitor: str
    safe_stop: str


@dataclass(frozen=True, config=DEVICE_SCHEMA_CONFIG)
class DeviceConfig:
    component_type: Annotated[str, Field(min_length=1)]
    capabilities: CapabilityConfig
    libraries: tuple[LibraryConfig, ...]
    pins: Mapping[Annotated[str, Field(min_length=1)], PinConfig]
    state: StateConfig
    commands: tuple[CommandConfig, ...]
    firmware: FirmwareConfig
    verification: VerificationConfig
    stream: StreamConfig

    def __post_init__(self) -> None:
        object.__setattr__(self, "pins", MappingProxyType(dict(self.pins)))

    @model_validator(mode="after")
    def validate_payload_contracts(self):
        for command in self.commands:
            if len(set(command.response_fields)) != len(command.response_fields):
                raise ValueError("Duplicate command response field")
            if not set(command.response_fields) <= self.state.fields.keys():
                raise ValueError("Command response references an undeclared state field")
        if self.capabilities.streaming:
            if len(self.stream.payload_fields) != 1:
                raise ValueError("Stream storage requires exactly one declared payload field")
        elif self.stream.payload_fields:
            raise ValueError("Non-streaming devices cannot declare stream payload fields")
        if not set(self.stream.payload_fields) <= self.state.fields.keys():
            raise ValueError("Stream references an undeclared state field")
        return self

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "DeviceConfig":
        return TypeAdapter(cls).validate_json(json.dumps(data))
