from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


class HardwareSystemValidator:
    @classmethod
    def validate(cls, hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        errors.extend(cls._validate_identity(hardware_system))
        errors.extend(cls._validate_microcontrollers(hardware_system))
        errors.extend(cls._validate_cameras(hardware_system))
        errors.extend(cls._validate_models(hardware_system))
        errors.extend(cls._validate_movement_system_names(hardware_system))
        return errors

    @staticmethod
    def registered_connections(
        hardware_system: HardwareSystem,
    ) -> dict[str, Connection]:
        return {
            connection.name.strip().casefold(): connection
            for microcontroller in hardware_system.microcontrollers
            for connection in microcontroller.connections
            if connection.name.strip()
        }

    @staticmethod
    def _validate_identity(hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        if not hardware_system.id.strip():
            errors.append("hardware_system.id: cannot be empty")
        if not hardware_system.name.strip():
            errors.append("hardware_system.name: cannot be empty")
        return errors

    @classmethod
    def _validate_microcontrollers(
        cls,
        hardware_system: HardwareSystem,
    ) -> list[str]:
        errors: list[str] = []
        microcontroller_ids: set[str] = set()
        connection_owners: dict[str, str] = {}

        for microcontroller in hardware_system.microcontrollers:
            microcontroller_id = microcontroller.id.strip()
            path = f"microcontrollers[{microcontroller_id or microcontroller.name}]"

            if not microcontroller_id:
                errors.append(f"{path}.id: cannot be empty")
            elif microcontroller_id in microcontroller_ids:
                errors.append(f"{path}.id: duplicate ID: {microcontroller_id}")
            else:
                microcontroller_ids.add(microcontroller_id)

            if microcontroller.hardware_system_id != hardware_system.id:
                errors.append(
                    f"{path}.hardware_system_id: expected {hardware_system.id}, "
                    f"got {microcontroller.hardware_system_id}"
                )

            errors.extend(
                cls._validate_connections(
                    microcontroller_id=microcontroller_id,
                    connections=microcontroller.connections,
                    connection_owners=connection_owners,
                )
            )

        return errors

    @staticmethod
    def _validate_connections(
        *,
        microcontroller_id: str,
        connections: list[Connection],
        connection_owners: dict[str, str],
    ) -> list[str]:
        errors: list[str] = []
        connection_names: set[str] = set()
        used_pins: set[str] = set()

        for connection in connections:
            connection_name = connection.name.strip()
            normalized_name = connection_name.casefold()
            path = (
                f"microcontrollers[{microcontroller_id}]."
                f"connections[{connection_name or '<empty>'}]"
            )

            if not connection_name:
                errors.append(f"{path}.name: cannot be empty")
            elif normalized_name in connection_names:
                errors.append(f"{path}.name: duplicate connection name")
            else:
                connection_names.add(normalized_name)

            existing_owner = connection_owners.get(normalized_name)
            if (
                normalized_name
                and existing_owner is not None
                and existing_owner != microcontroller_id
            ):
                errors.append(
                    f"{path}.name: already used by microcontroller "
                    f"{existing_owner}"
                )
            elif normalized_name:
                connection_owners[normalized_name] = microcontroller_id

            if connection.microcontroller_id != microcontroller_id:
                errors.append(
                    f"{path}.microcontroller_id: expected {microcontroller_id}, "
                    f"got {connection.microcontroller_id}"
                )

            if not connection.component_type.strip():
                errors.append(f"{path}.component_type: cannot be empty")

            for pin_name, pin in connection.pins.items():
                pin_path = f"{path}.pins[{pin_name}]"
                if not pin.strip():
                    errors.append(f"{pin_path}: cannot be empty")
                elif pin in used_pins:
                    errors.append(
                        f"{pin_path}: pin already in use on microcontroller "
                        f"{microcontroller_id}: {pin}"
                    )
                else:
                    used_pins.add(pin)

        return errors

    @staticmethod
    def _validate_cameras(hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        camera_ids: set[str] = set()

        for camera in hardware_system.cameras:
            camera_id = camera.camera_id.strip()
            path = f"cameras[{camera_id or camera.name}]"
            if not camera_id:
                errors.append(f"{path}.camera_id: cannot be empty")
            elif camera_id in camera_ids:
                errors.append(f"{path}.camera_id: duplicate ID: {camera_id}")
            else:
                camera_ids.add(camera_id)

            if not camera.name.strip():
                errors.append(f"{path}.name: cannot be empty")

        return errors

    @staticmethod
    def _validate_models(hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        model_ids: set[str] = set()
        model_names: set[str] = set()
        camera_ids = {
            camera.camera_id.strip()
            for camera in hardware_system.cameras
        }

        for model in hardware_system.models:
            model_id = model.model_id.strip()
            model_name = model.name.strip()
            normalized_model_name = model_name.casefold()
            path = f"models[{model_id or model_name or '<empty>'}]"

            if not model_id:
                errors.append(f"{path}.model_id: cannot be empty")
            elif model_id in model_ids:
                errors.append(f"{path}.model_id: duplicate ID: {model_id}")
            else:
                model_ids.add(model_id)

            if not model_name:
                errors.append(f"{path}.name: cannot be empty")
            elif normalized_model_name in model_names:
                errors.append(f"{path}.name: duplicate model name: {model_name}")
            else:
                model_names.add(normalized_model_name)

            subscribed_camera_id = model.subscribed_camera.camera_id.strip()
            if subscribed_camera_id not in camera_ids:
                errors.append(
                    f"{path}.subscribed_camera: camera is not registered: "
                    f"{subscribed_camera_id}"
                )

        return errors

    @staticmethod
    def _validate_movement_system_names(
        hardware_system: HardwareSystem,
    ) -> list[str]:
        errors: list[str] = []
        movement_system_names: set[str] = set()

        for movement_system in hardware_system.movement_systems:
            name = movement_system.name.strip()
            normalized_name = name.casefold()
            path = f"movement_systems[{name or '<empty>'}]"
            if not name:
                errors.append(f"{path}.name: cannot be empty")
            elif normalized_name in movement_system_names:
                errors.append(f"{path}.name: duplicate movement system name")
            else:
                movement_system_names.add(normalized_name)

        return errors
