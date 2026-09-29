from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


def is_ascii_letter(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def is_ascii_digit(character: str) -> bool:
    return "0" <= character <= "9"


def is_firmware_identifier(value: str) -> bool:
    if not value:
        return False
    if value[0] != "_" and not is_ascii_letter(value[0]):
        return False
    return all(
        character == "_"
        or is_ascii_letter(character)
        or is_ascii_digit(character)
        for character in value[1:]
    )


class HardwareSystemValidator:
    @classmethod
    def validate(cls, hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        errors.extend(cls.validate_identity(hardware_system))
        errors.extend(cls.validate_microcontrollers(hardware_system))
        errors.extend(cls.validate_cameras(hardware_system))
        errors.extend(cls.validate_models(hardware_system))
        errors.extend(cls.validate_movement_system_names(hardware_system))
        return errors

    @staticmethod
    def registered_connections(
        hardware_system: HardwareSystem,
    ) -> dict[tuple[str, str], Connection]:
        return {
            (
                microcontroller.id,
                connection.name.strip().casefold(),
            ): connection
            for microcontroller in hardware_system.microcontrollers
            for connection in microcontroller.connections
            if isinstance(connection.name, str) and connection.name.strip()
        }

    @classmethod
    def validate_microcontroller_connections(
        cls,
        microcontroller: object,
    ) -> list[str]:
        return cls.validate_connections(
            microcontroller_id=microcontroller.id,
            connections=microcontroller.connections,
            connection_owners={},
        )

    @staticmethod
    def validate_identity(hardware_system: HardwareSystem) -> list[str]:
        errors: list[str] = []
        if not hardware_system.id.strip():
            errors.append("hardware_system.id: cannot be empty")
        if not hardware_system.name.strip():
            errors.append("hardware_system.name: cannot be empty")
        return errors

    @classmethod
    def validate_microcontrollers(
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
                cls.validate_connections(
                    microcontroller_id=microcontroller_id,
                    connections=microcontroller.connections,
                    connection_owners=connection_owners,
                )
            )

        return errors

    @staticmethod
    def validate_connections(
        *,
        microcontroller_id: str,
        connections: list[Connection],
        connection_owners: dict[str, str],
    ) -> list[str]:
        errors: list[str] = []
        connection_names: set[str] = set()

        for connection in connections:
            connection_name = (
                connection.name.strip()
                if isinstance(connection.name, str)
                else ""
            )
            normalized_name = connection_name.casefold()
            path = (
                f"microcontrollers[{microcontroller_id}]."
                f"connections[{connection_name or '<empty>'}]"
            )

            if not isinstance(connection.name, str):
                errors.append(f"{path}.name: must be a string")
            elif not connection_name:
                errors.append(f"{path}.name: cannot be empty")
            elif not is_firmware_identifier(connection_name):
                errors.append(
                    f"{path}.name: must be a valid firmware identifier"
                )
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

            if not isinstance(connection.component_type, str):
                errors.append(f"{path}.component_type: must be a string")
            elif not connection.component_type.strip():
                errors.append(f"{path}.component_type: cannot be empty")

        return errors

    @staticmethod
    def validate_cameras(hardware_system: HardwareSystem) -> list[str]:
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
    def validate_models(hardware_system: HardwareSystem) -> list[str]:
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
    def validate_movement_system_names(
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
