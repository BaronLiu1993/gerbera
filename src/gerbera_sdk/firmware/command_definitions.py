from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import CommandSpec
from gerbera_sdk.models.hardware.connection import Connection


def command_specs(connection: Connection) -> list[CommandSpec]:
    return list(get_device_builder(connection.component_type).required_commands(connection))
