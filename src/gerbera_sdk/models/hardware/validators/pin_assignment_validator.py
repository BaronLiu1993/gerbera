from collections.abc import Mapping

from gerbera_sdk.firmware.board_definitions import BoardRegistry
from gerbera_sdk.firmware.configurations import DeviceRegistry
from gerbera_sdk.firmware.firmware_schema import PinAssignmentMode
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


class PinAssignmentValidator:
    @classmethod
    def validate(
        cls,
        hardware_system: HardwareSystem,
        device_registry: DeviceRegistry,
        board_registry: BoardRegistry,
    ) -> list[str]:
        errors: list[str] = []

        for microcontroller in hardware_system.microcontrollers:
            errors.extend(
                cls.validate_microcontroller(
                    microcontroller,
                    device_registry,
                    board_registry,
                )
            )

        return errors

    @staticmethod
    def validate_microcontroller(
        microcontroller: Microcontroller,
        device_registry: DeviceRegistry,
        board_registry: BoardRegistry,
    ) -> list[str]:
        errors: list[str] = []
        microcontroller_id = microcontroller.id
        board_path = f"microcontrollers[{microcontroller_id}]"
        fqbn = getattr(microcontroller, "fqbn", None)
        if not isinstance(fqbn, str) or not fqbn:
            return [f"{board_path}.fqbn: cannot be empty"]

        try:
            board_definition = board_registry.get_definition(fqbn)
        except ValueError:
            return [
                f"{board_path}.fqbn: unsupported microcontroller: {fqbn}"
            ]

        claimed_pins: dict[str, str] = {}
        for connection in microcontroller.connections:
            connection_path = (
                f"{board_path}.connections["
                f"{connection.name or '<empty>'}]"
            )
            component_type = connection.component_type
            if not isinstance(component_type, str) or not component_type:
                errors.append(
                    f"{connection_path}.component_type: must be a non-empty "
                    "string"
                )
                continue
            try:
                device_definition = device_registry.get_definition(
                    component_type
                )
            except ValueError:
                errors.append(
                    f"{connection_path}.component_type: unsupported "
                    f"component type: {component_type}"
                )
                continue

            if not isinstance(connection.pins, Mapping):
                errors.append(
                    f"{connection_path}.pins: must be a mapping"
                )
                continue

            expected_pins = set(device_definition.config.pins)
            configured_pins: set[str] = set()
            for logical_pin in connection.pins:
                logical_pin_path = (
                    f"{connection_path}.pins[{logical_pin}]"
                )
                if not isinstance(logical_pin, str) or not logical_pin:
                    errors.append(
                        f"{logical_pin_path}: logical pin must be a non-empty "
                        "string"
                    )
                    continue
                if logical_pin != logical_pin.strip():
                    errors.append(
                        f"{logical_pin_path}: logical pin cannot contain "
                        "surrounding whitespace"
                    )
                    continue
                configured_pins.add(logical_pin)

            for pin_name in sorted(expected_pins - configured_pins):
                errors.append(
                    f"{connection_path}.pins: missing required logical "
                    f"pin: {pin_name}"
                )
            for pin_name in sorted(configured_pins - expected_pins):
                errors.append(
                    f"{connection_path}.pins[{pin_name}]: unexpected "
                    "logical pin"
                )

            for logical_pin, physical_pin in connection.pins.items():
                pin_path = f"{connection_path}.pins[{logical_pin}]"
                if logical_pin not in configured_pins:
                    continue
                if not isinstance(physical_pin, str):
                    errors.append(f"{pin_path}: must be a string")
                    continue
                if not physical_pin:
                    errors.append(f"{pin_path}: cannot be empty")
                    continue
                if physical_pin != physical_pin.strip():
                    errors.append(
                        f"{pin_path}: cannot contain surrounding whitespace"
                    )
                    continue

                try:
                    board_pin = board_definition.resolve_pin(physical_pin)
                except ValueError:
                    errors.append(
                        f"{pin_path}: unknown physical pin for "
                        f"{board_definition.fqbn}: {physical_pin}"
                    )
                    continue

                if board_pin.reserved_by is not None:
                    errors.append(
                        f"{pin_path}: physical pin "
                        f"{board_pin.canonical_name} is reserved by "
                        f"{board_pin.reserved_by}"
                    )

                pin_config = device_definition.config.pins.get(logical_pin)
                if pin_config is None:
                    continue

                missing_capabilities = (
                    pin_config.capabilities - board_pin.capabilities
                )
                if missing_capabilities:
                    capability_names = ", ".join(
                        sorted(
                            capability.value
                            for capability in missing_capabilities
                        )
                    )
                    errors.append(
                        f"{pin_path}: physical pin "
                        f"{board_pin.canonical_name} is missing required "
                        f"capabilities: {capability_names}"
                    )

                if pin_config.assignment == PinAssignmentMode.EXCLUSIVE:
                    existing_path = claimed_pins.get(board_pin.canonical_name)
                    if existing_path is not None:
                        errors.append(
                            f"{pin_path}: physical pin "
                            f"{board_pin.canonical_name} is already assigned "
                            f"to {existing_path}"
                        )
                    else:
                        claimed_pins[board_pin.canonical_name] = pin_path

        return errors
