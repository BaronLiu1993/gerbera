from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def validate_hardware_system(hardware_system: HardwareSystem) -> str | None:
    microcontroller_ids: set[str] = set()
    camera_ids: set[str] = set()
    connection_owners: dict[str, str] = {}

    for microcontroller in hardware_system.microcontrollers:
        microcontroller_id = microcontroller.id
        if microcontroller_id in microcontroller_ids:
            return f"Duplicate microcontroller id: {microcontroller_id}"
        microcontroller_ids.add(microcontroller_id)
        error = validate_microcontroller(microcontroller)
        if error is not None:
            return error

        for connection in microcontroller.connections:
            normalized_name = connection.name.strip().lower()
            existing_owner = connection_owners.get(normalized_name)
            if existing_owner is not None:
                return (
                    f"Connection name must be globally unique: "
                    f"{connection.name}. Used by microcontrollers "
                    f"{existing_owner} and {microcontroller_id}"
                )
            connection_owners[normalized_name] = microcontroller_id

    for camera in hardware_system.cameras:
        if camera.camera_id in camera_ids:
            return f"Duplicate camera id: {camera.camera_id}"
        camera_ids.add(camera.camera_id)

    return None


def validate_microcontroller(microcontroller: Microcontroller) -> str | None:
    connection_names: set[str] = set()
    used_pins: set[str] = set()

    for connection in microcontroller.connections:
        error = validate_connection_and_pins(
            connection=connection,
            connection_names=connection_names,
            used_pins=used_pins,
            microcontroller_id=microcontroller.id,
        )
        if error is not None:
            return error

    return None


def validate_connection_and_pins(
    *,
    connection: Connection,
    connection_names: set[str],
    used_pins: set[str],
    microcontroller_id: str,
) -> str | None:
    normalized_name = connection.name.strip().lower()
    if not normalized_name:
        return "Connection name cannot be empty"

    if normalized_name in connection_names:
        return f"Duplicate connection name on board {microcontroller_id}: {connection.name}"
    connection_names.add(normalized_name)

    for pin in connection.pins.values():
        if pin in used_pins:
            return f"Pin already in use on board {microcontroller_id}: {pin}"
        used_pins.add(pin)

    return None
