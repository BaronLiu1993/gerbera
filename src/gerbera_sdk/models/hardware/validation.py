from collections.abc import Iterable

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def validate_hardware_system(hardware_system: HardwareSystem) -> str | None:
    error = validate_unique_microcontroller_ids(hardware_system)
    if error is not None:
        return error

    error = validate_unique_values(
        values=(camera.camera_id for camera in hardware_system.cameras),
        label="camera id",
    )
    if error is not None:
        return error

    for microcontroller in hardware_system.microcontrollers:
        error = validate_microcontroller(microcontroller)
        if error is not None:
            return error

    return validate_globally_unique_connection_names(hardware_system)


def validate_unique_microcontroller_ids(
    hardware_system: HardwareSystem,
) -> str | None:
    try:
        return validate_unique_values(
            values=(
                microcontroller.id
                for microcontroller in hardware_system.microcontrollers
            ),
            label="microcontroller id",
        )
    except Exception as exc:
        return str(exc)


def validate_globally_unique_connection_names(
    hardware_system: HardwareSystem,
) -> str | None:
    connection_owners: dict[str, str] = {}

    for microcontroller in hardware_system.microcontrollers:
        for connection in microcontroller.connections:
            normalized_name = connection.name.strip().lower()
            if not normalized_name:
                return "Connection name cannot be empty"

            existing_owner = connection_owners.get(normalized_name)
            if existing_owner is not None:
                return (
                    f"Connection name must be globally unique: "
                    f"{connection.name}. Used by microcontrollers "
                    f"{existing_owner} and {microcontroller.id}"
                )

            connection_owners[normalized_name] = microcontroller.id

    return None


def validate_microcontroller(microcontroller: Microcontroller) -> str | None:
    error = validate_unique_values(
        values=(connection.name for connection in microcontroller.connections),
        label=f"connection name on board {microcontroller.id}",
    )
    if error is not None:
        return error

    return validate_unique_pins(microcontroller)


def validate_unique_values(values: Iterable[str], label: str) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return f"Duplicate {label}: {value}"
        seen.add(value)

    return None


def validate_unique_pins(microcontroller: Microcontroller) -> str | None:
    used_pins: set[str] = set()
    for connection in microcontroller.connections:
        for pin in connection.pins.values():
            if pin in used_pins:
                return f"Pin already in use on board {microcontroller.id}: {pin}"
            used_pins.add(pin)

    return None
