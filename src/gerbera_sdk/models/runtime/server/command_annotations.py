from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import CommandSpec
from gerbera_sdk.models.hardware.connection import Connection


def command_annotations(connection: Connection, command: CommandSpec) -> ToolAnnotations:
    builder = get_device_builder(connection.component_type)
    builder.validate_required_pins(connection)
    annotations = builder.command_config(command.method, connection).annotations
    return ToolAnnotations(
        title=builder.render(annotations.title, connection),
        readOnlyHint=annotations.read_only_hint,
        openWorldHint=annotations.open_world_hint,
    )
