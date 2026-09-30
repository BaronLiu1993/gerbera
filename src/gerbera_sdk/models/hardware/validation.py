import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType

from gerbera_sdk.firmware.board_definitions import BOARD_REGISTRY, BoardDefinition
from gerbera_sdk.firmware.configurations import DEVICE_REGISTRY
from gerbera_sdk.firmware.firmware_schema import (
    BoardTransportKind,
    GERBERA_PROTOCOL_VERSION,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.hardware.microcontroller import (
    RuntimeTransportConfig,
    RuntimeWatchdogConfig,
)
from gerbera_sdk.models.hardware.hardware_plan import (
    ConnectionKey,
    EventRouteKey,
    HardwarePlan,
    ResolvedBoard,
    ResolvedConnection,
    ResolvedPinAssignment,
    ResolvedVerification,
)
from gerbera_sdk.utils import build_connection_event_name
from gerbera_sdk.models.hardware.validators import (
    DefinitionValidator,
    HardwareSystemValidator,
    MovementSystemValidator,
    PinAssignmentValidator,
)


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...]

    @classmethod
    def from_errors(cls, errors: list[str]) -> "ValidationResult":
        return cls(errors=tuple(errors[:1]))

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            formatted_errors = "\n".join(
                f"- {error}" for error in self.errors
            )
            raise ValueError(
                f"Hardware system validation failed:\n{formatted_errors}"
            )


@dataclass(frozen=True)
class BoardContractIdentity:
    microcontroller_id: str
    baud_rate: int
    definition: BoardDefinition
    runtime_transport: RuntimeTransportConfig | None = None


class HardwareValidationFacade:
    @staticmethod
    def validate(hardware_system: HardwareSystem) -> ValidationResult:
        errors = DefinitionValidator.validate(
            DEVICE_REGISTRY,
            BOARD_REGISTRY,
        )
        if errors:
            return ValidationResult.from_errors(errors)

        errors = HardwareSystemValidator.validate(hardware_system)
        if errors:
            return ValidationResult.from_errors(errors)

        for microcontroller in hardware_system.microcontrollers:
            errors = HardwareContractCompiler.validate_watchdog(microcontroller)
            if errors:
                return ValidationResult.from_errors(errors)
            errors = HardwareContractCompiler.validate_transport(
                microcontroller
            )
            if errors:
                return ValidationResult.from_errors(errors)

        errors = PinAssignmentValidator.validate(
            hardware_system,
            DEVICE_REGISTRY,
            BOARD_REGISTRY,
        )
        if errors:
            return ValidationResult.from_errors(errors)

        registered_connections = (
            HardwareSystemValidator.registered_connections(hardware_system)
        )

        for movement_system in hardware_system.movement_systems:
            errors = MovementSystemValidator.validate(
                movement_system,
                registered_connections,
            )
            if errors:
                return ValidationResult.from_errors(errors)

        return ValidationResult(errors=())


class HardwareContractCompiler:
    @classmethod
    def compile(cls, hardware_system: HardwareSystem) -> HardwarePlan:
        validation = HardwareValidationFacade.validate(hardware_system)
        validation.raise_for_errors()

        boards = tuple(
            cls.resolve_board(microcontroller)
            for microcontroller in hardware_system.microcontrollers
        )
        boards_by_id: dict[str, ResolvedBoard] = {}
        connections_by_key: dict[ConnectionKey, ResolvedConnection] = {}
        connections_by_event_route: dict[
            EventRouteKey,
            ResolvedConnection,
        ] = {}

        for board in boards:
            if board.microcontroller_id in boards_by_id:
                raise ValueError(
                    f"Duplicate microcontroller ID: {board.microcontroller_id}"
                )
            boards_by_id[board.microcontroller_id] = board

            for connection in board.connections:
                if connection.connection_key in connections_by_key:
                    raise ValueError(
                        f"Duplicate connection key: {connection.connection_key}"
                    )
                event_route = (board.microcontroller_id, connection.event_name)
                if event_route in connections_by_event_route:
                    raise ValueError(f"Duplicate event route: {event_route}")
                connections_by_key[connection.connection_key] = connection
                connections_by_event_route[event_route] = connection

        return HardwarePlan(
            hardware_system_id=hardware_system.id,
            boards=boards,
            boards_by_id=MappingProxyType(boards_by_id),
            connections_by_key=MappingProxyType(connections_by_key),
            connections_by_event_route=MappingProxyType(
                connections_by_event_route
            ),
        )

    @classmethod
    def compile_microcontroller(
        cls,
        microcontroller: Microcontroller,
    ) -> ResolvedBoard:
        definition_errors = DefinitionValidator.validate(
            DEVICE_REGISTRY,
            BOARD_REGISTRY,
        )
        ValidationResult.from_errors(definition_errors).raise_for_errors()

        connection_errors = (
            HardwareSystemValidator.validate_microcontroller_connections(
                microcontroller
            )
        )
        ValidationResult.from_errors(connection_errors).raise_for_errors()

        pin_errors = PinAssignmentValidator.validate_microcontroller(
            microcontroller,
            DEVICE_REGISTRY,
            BOARD_REGISTRY,
        )
        ValidationResult.from_errors(pin_errors).raise_for_errors()
        watchdog_errors = cls.validate_watchdog(microcontroller)
        ValidationResult.from_errors(watchdog_errors).raise_for_errors()
        transport_errors = cls.validate_transport(microcontroller)
        ValidationResult.from_errors(transport_errors).raise_for_errors()
        return cls.resolve_board(microcontroller)

    @staticmethod
    def resolve_board(microcontroller: Microcontroller) -> ResolvedBoard:
        microcontroller_id = microcontroller.id
        board_definition = BOARD_REGISTRY.get_definition(
            microcontroller.fqbn
        )
        resolved_connections: list[ResolvedConnection] = []

        for connection in sorted(
            microcontroller.connections,
            key=lambda item: item.name,
        ):
            device_definition = DEVICE_REGISTRY.get_definition(
                connection.component_type
            )
            assignments = tuple(
                ResolvedPinAssignment(
                    logical_name=logical_pin,
                    physical_pin=board_definition.resolve_pin(
                        connection.pins[logical_pin]
                    ).canonical_name,
                    mode=pin_config.mode,
                    capabilities=pin_config.capabilities,
                    assignment=pin_config.assignment,
                )
                for logical_pin, pin_config in sorted(
                    device_definition.config.pins.items()
                )
            )
            resolved_connections.append(
                ResolvedConnection(
                    connection_key=(microcontroller_id, connection.name),
                    event_name=build_connection_event_name(
                        microcontroller_id=microcontroller_id,
                        connection_name=connection.name,
                    ),
                    name=connection.name,
                    component_type=connection.component_type,
                    description=connection.description,
                    microcontroller_id=microcontroller_id,
                    stream=connection.stream,
                    pin_assignments=assignments,
                    verification=ResolvedVerification(
                        startup_timeout_ms=(
                            device_definition.config.verification.startup_timeout_ms
                        ),
                        monitor_interval_ms=(
                            device_definition.config.verification.monitor_interval_ms
                        ),
                        check=device_definition.config.verification.check,
                        monitor=device_definition.config.verification.monitor,
                        safe_stop=device_definition.config.verification.safe_stop,
                    ),
                    device_definition=device_definition,
                    source_connection=connection,
                )
            )

        connections = tuple(resolved_connections)
        runtime_transport = microcontroller.active_runtime_transport
        return ResolvedBoard(
            microcontroller_id=microcontroller_id,
            name=microcontroller.name,
            port=runtime_transport.port,
            baud_rate=microcontroller.baud_rate,
            definition=board_definition,
            connections=connections,
            watchdog=microcontroller.watchdog,
            upload_port=microcontroller.firmware_upload_port,
            runtime_transport=runtime_transport,
            contract_digest=HardwareContractCompiler.calculate_board_digest(
                BoardContractIdentity(
                    microcontroller_id=microcontroller_id,
                    baud_rate=microcontroller.baud_rate,
                    definition=board_definition,
                    runtime_transport=runtime_transport,
                ),
                connections,
                microcontroller.watchdog,
            ),
        )

    @staticmethod
    def calculate_board_digest(
        identity: BoardContractIdentity,
        connections: tuple[ResolvedConnection, ...],
        watchdog: RuntimeWatchdogConfig,
    ) -> str:
        payload = {
            "baud_rate": identity.baud_rate,
            "board_includes": list(identity.definition.includes),
            "connections": [
                HardwareContractCompiler.connection_contract_payload(connection)
                for connection in connections
            ],
            "fqbn": identity.definition.fqbn,
            "microcontroller_id": identity.microcontroller_id,
            "protocol_version": GERBERA_PROTOCOL_VERSION,
            "runtime_transport": (
                HardwareContractCompiler.transport_contract_payload(
                    identity.runtime_transport
                )
            ),
            "watchdog": {
                "heartbeat_interval_ms": watchdog.heartbeat_interval_ms,
                "heartbeat_timeout_ms": watchdog.heartbeat_timeout_ms,
            },
        }
        serialized_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized_payload.encode()).hexdigest()

    @staticmethod
    def transport_contract_payload(
        transport: RuntimeTransportConfig | None,
    ) -> dict[str, str | None]:
        resolved_transport = transport or RuntimeTransportConfig.usb_serial("")
        return {
            "device_name": resolved_transport.device_name,
            "kind": resolved_transport.kind.value,
        }

    @staticmethod
    def validate_transport(
        microcontroller: Microcontroller,
    ) -> list[str]:
        transport = microcontroller.active_runtime_transport
        path = f"microcontrollers[{microcontroller.id}].runtime_transport"
        if not transport.port.strip():
            return [f"{path}.port: cannot be empty"]

        board_definition = BOARD_REGISTRY.get_definition(
            microcontroller.fqbn
        )
        if transport.kind not in board_definition.supported_transports:
            return [
                f"{path}.kind: {transport.kind.value} is not supported by "
                f"{microcontroller.fqbn}"
            ]

        if transport.kind == BoardTransportKind.BLUETOOTH_CLASSIC:
            device_name = transport.device_name or ""
            if not device_name.strip():
                return [f"{path}.device_name: cannot be empty"]
            if "\n" in device_name or "\r" in device_name:
                return [f"{path}.device_name: cannot contain newlines"]
        return []

    @staticmethod
    def connection_contract_payload(
        connection: ResolvedConnection,
    ) -> dict[str, object]:
        config = connection.device_definition.config
        firmware = config.firmware
        return {
            "commands": [
                {
                    "enabled_when": command.enabled_when,
                    "method": command.method,
                    "params": {
                        name: {
                            "max": parameter.max,
                            "min": parameter.min,
                            "required": parameter.required,
                        }
                        for name, parameter in sorted(command.params.items())
                    },
                }
                for command in config.commands
            ],
            "component_type": connection.component_type,
            "firmware": {
                "definitions": firmware.definitions,
                "definitions_when_streaming": (
                    firmware.definitions_when_streaming
                ),
                "handlers": firmware.handlers,
                "setup": list(firmware.setup),
                "setup_when_streaming": list(firmware.setup_when_streaming),
                "stream_loop_when_streaming": (
                    firmware.stream_loop_when_streaming
                ),
            },
            "libraries": [
                {"include": library.include, "install": library.install}
                for library in config.libraries
            ],
            "name": connection.name,
            "pins": [
                HardwareContractCompiler.pin_contract_payload(pin)
                for pin in connection.pin_assignments
            ],
            "stream": connection.stream,
            "verification": {
                "check": connection.verification.check,
                "monitor": connection.verification.monitor,
                "monitor_interval_ms": (
                    connection.verification.monitor_interval_ms
                ),
                "safe_stop": connection.verification.safe_stop,
                "startup_timeout_ms": (
                    connection.verification.startup_timeout_ms
                ),
            },
        }

    @staticmethod
    def validate_watchdog(microcontroller: Microcontroller) -> list[str]:
        watchdog = microcontroller.watchdog
        path = f"microcontrollers[{microcontroller.id}].watchdog"
        interval = watchdog.heartbeat_interval_ms
        timeout = watchdog.heartbeat_timeout_ms
        if (
            not isinstance(interval, int)
            or isinstance(interval, bool)
            or interval <= 0
        ):
            return [f"{path}.heartbeat_interval_ms: must be a positive integer"]
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            return [f"{path}.heartbeat_timeout_ms: must be a positive integer"]
        if timeout <= interval:
            return [f"{path}: timeout must exceed interval"]
        if timeout < interval * 2:
            return [f"{path}: timeout must allow at least one interval of jitter"]

        for connection in microcontroller.connections:
            verification = DEVICE_REGISTRY.get_definition(
                connection.component_type
            ).config.verification
            if verification.startup_timeout_ms >= timeout:
                return [
                    f"{path}: {connection.name} startup timeout must be shorter "
                    "than the heartbeat timeout"
                ]
            if verification.monitor_interval_ms >= timeout:
                return [
                    f"{path}: {connection.name} monitor interval must be shorter "
                    "than the heartbeat timeout"
                ]
        return []

    @staticmethod
    def pin_contract_payload(
        pin: ResolvedPinAssignment,
    ) -> dict[str, object]:
        return {
            "assignment": pin.assignment.value,
            "capabilities": sorted(
                capability.value for capability in pin.capabilities
            ),
            "logical_name": pin.logical_name,
            "mode": pin.mode.value,
            "physical_pin": pin.physical_pin,
        }
