from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.firmware_schema import CommandSpec
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder
from gerbera_sdk.models.hardware.connection import Connection


class MG996RFirmwareBuilder(SG90FirmwareBuilder):
    def annotations(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> ToolAnnotations:
        annotations = super().annotations(connection, command)
        return annotations.model_copy(
            update={"title": f"Set {connection.name} MG996R servo angle"}
        )
