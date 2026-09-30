from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable

from gerbera_sdk.firmware.board_definitions import BoardDefinition
from gerbera_sdk.firmware.configurations import DeviceDefinition
from gerbera_sdk.firmware.firmware_schema import (
    PinAssignmentMode,
    PinCapability,
    PinMode,
)
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import (
    RuntimeTransportConfig,
    RuntimeWatchdogConfig,
)

ConnectionKey = tuple[str, str]
EventRouteKey = tuple[str, str]
StateKey = tuple[str, str, str]


@dataclass(frozen=True)
class ResolvedPinAssignment:
    logical_name: str
    physical_pin: str
    mode: PinMode
    capabilities: frozenset[PinCapability]
    assignment: PinAssignmentMode


@dataclass(frozen=True)
class ResolvedVerification:
    startup_timeout_ms: int
    monitor_interval_ms: int
    check: str
    monitor: str
    safe_stop: str


@dataclass(frozen=True)
class ResolvedConnection:
    connection_key: ConnectionKey
    event_name: str
    name: str
    component_type: str
    description: str
    microcontroller_id: str
    stream: bool
    pin_assignments: tuple[ResolvedPinAssignment, ...]
    verification: ResolvedVerification
    device_definition: DeviceDefinition
    source_connection: Connection = field(repr=False, compare=False)

    @property
    def pins(self) -> dict[str, str]:
        return {
            assignment.logical_name: assignment.physical_pin
            for assignment in self.pin_assignments
        }

    @property
    def stream_enabled(self) -> bool:
        return self.stream

    def register_action(
        self,
        action: str,
        callback: Callable[[dict[str, object]], dict[str, object]],
    ) -> None:
        self.source_connection.register_action(action, callback)

    def perform_action(
        self,
        action: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        return self.source_connection.perform_action(action, params)


@dataclass(frozen=True)
class ResolvedBoard:
    microcontroller_id: str
    name: str
    port: str
    baud_rate: int
    definition: BoardDefinition
    connections: tuple[ResolvedConnection, ...]
    watchdog: RuntimeWatchdogConfig
    contract_digest: str
    upload_port: str | None = None
    runtime_transport: RuntimeTransportConfig | None = None

    @property
    def fqbn(self) -> str:
        return self.definition.fqbn

    @property
    def firmware_upload_port(self) -> str:
        return self.upload_port or self.port

    @property
    def active_runtime_transport(self) -> RuntimeTransportConfig:
        return self.runtime_transport or RuntimeTransportConfig.usb_serial(
            self.port
        )


@dataclass(frozen=True)
class HardwarePlan:
    hardware_system_id: str
    boards: tuple[ResolvedBoard, ...]
    boards_by_id: Mapping[str, ResolvedBoard]
    connections_by_key: Mapping[ConnectionKey, ResolvedConnection]
    connections_by_event_route: Mapping[EventRouteKey, ResolvedConnection]
