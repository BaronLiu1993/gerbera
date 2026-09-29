from gerbera_sdk.firmware.board_definitions import BoardRegistry
from gerbera_sdk.firmware.configurations import DeviceRegistry
from gerbera_sdk.firmware.firmware_schema import PinCapability, PinMode
from gerbera_sdk.models.hardware.validators.hardware_system_validator import (
    is_firmware_identifier,
)


PIN_PLACEHOLDER_PREFIX = "{pins."


def extract_pin_placeholders(value: str) -> tuple[str, ...]:
    placeholders: list[str] = []
    search_start = 0

    while True:
        placeholder_start = value.find(
            PIN_PLACEHOLDER_PREFIX,
            search_start,
        )
        if placeholder_start == -1:
            return tuple(placeholders)

        pin_name_start = placeholder_start + len(PIN_PLACEHOLDER_PREFIX)
        placeholder_end = value.find("}", pin_name_start)
        if placeholder_end == -1:
            return tuple(placeholders)

        pin_name = value[pin_name_start:placeholder_end]
        if pin_name and "{" not in pin_name:
            placeholders.append(pin_name)

        search_start = placeholder_end + 1


class DefinitionValidator:
    @classmethod
    def validate(
        cls,
        device_registry: DeviceRegistry,
        board_registry: BoardRegistry,
    ) -> list[str]:
        errors = cls.validate_device_definitions(device_registry)
        errors.extend(cls.validate_board_definitions(board_registry))
        return errors

    @staticmethod
    def validate_device_definitions(
        device_registry: DeviceRegistry,
    ) -> list[str]:
        errors: list[str] = []

        for definition in device_registry.definitions:
            path = f"device_definitions[{definition.component_type}]"
            if definition.config.component_type != definition.component_type:
                errors.append(
                    f"{path}.component_type: config declares "
                    f"{definition.config.component_type}"
                )
            if not is_firmware_identifier(definition.component_type):
                errors.append(
                    f"{path}.component_type: must be a valid firmware identifier"
                )

            declared_pins = set(definition.config.pins)
            for pin_name, pin_config in definition.config.pins.items():
                pin_path = f"{path}.pins[{pin_name}]"
                if (
                    pin_config.mode == PinMode.INPUT
                    and not pin_config.capabilities
                    & {
                        PinCapability.DIGITAL_INPUT,
                        PinCapability.ANALOG_INPUT,
                    }
                ):
                    errors.append(
                        f"{pin_path}: INPUT mode requires an input capability"
                    )
                if (
                    pin_config.mode == PinMode.OUTPUT
                    and not pin_config.capabilities
                    & {
                        PinCapability.DIGITAL_OUTPUT,
                        PinCapability.PWM_OUTPUT,
                    }
                ):
                    errors.append(
                        f"{pin_path}: OUTPUT mode requires an output capability"
                    )

            referenced_pins: set[str] = set()
            firmware = definition.config.firmware
            firmware_blocks = (
                firmware.definitions,
                firmware.definitions_when_streaming,
                firmware.stream_loop_when_streaming,
                *firmware.setup,
                *firmware.setup_when_streaming,
                *firmware.handlers.values(),
            )
            verification = definition.config.verification
            verification_blocks = (
                verification.check,
                verification.monitor,
                verification.safe_stop,
            )
            if (
                not isinstance(verification.startup_timeout_ms, int)
                or isinstance(verification.startup_timeout_ms, bool)
                or verification.startup_timeout_ms <= 0
            ):
                errors.append(
                    f"{path}.verification.startup_timeout_ms: must be a "
                    "positive integer"
                )
            if (
                not isinstance(verification.monitor_interval_ms, int)
                or isinstance(verification.monitor_interval_ms, bool)
                or verification.monitor_interval_ms <= 0
            ):
                errors.append(
                    f"{path}.verification.monitor_interval_ms: must be a "
                    "positive integer"
                )
            if not verification.check.strip():
                errors.append(f"{path}.verification.check: cannot be empty")
            if not verification.monitor.strip():
                errors.append(f"{path}.verification.monitor: cannot be empty")
            has_output = any(
                pin.mode == PinMode.OUTPUT
                for pin in definition.config.pins.values()
            )
            if has_output and not verification.safe_stop.strip():
                errors.append(
                    f"{path}.verification.safe_stop: cannot be empty for an "
                    "output device"
                )
            firmware_blocks += verification_blocks
            for block in firmware_blocks:
                referenced_pins.update(extract_pin_placeholders(block))

            for pin_name in sorted(referenced_pins - declared_pins):
                errors.append(
                    f"{path}.firmware: undeclared pin placeholder: {pin_name}"
                )

        return errors

    @staticmethod
    def validate_board_definitions(
        board_registry: BoardRegistry,
    ) -> list[str]:
        errors: list[str] = []

        for definition in board_registry.definitions:
            path = f"board_definitions[{definition.fqbn}]"
            for pin in definition.pins:
                pin_path = f"{path}.pins[{pin.canonical_name}]"
                if pin.canonical_name not in pin.aliases:
                    errors.append(
                        f"{pin_path}: aliases must contain the canonical pin"
                    )
                if not pin.capabilities:
                    errors.append(f"{pin_path}: must define capabilities")

        return errors
