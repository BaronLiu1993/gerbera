from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.firmware_schema import CommandSpec, ParameterSpec
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.firmware_schema import LibrarySpec, PinModeSpec
from gerbera_sdk.models.hardware.connection import Connection


class SG90FirmwareBuilder(BaseFirmwareBuilder):
    def required_libraries(self) -> list[LibrarySpec]:
        return [
            LibrarySpec(
                include="Servo.h",
                install="Servo",
            )
        ]

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        return []

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        _ = connection
        return [
            CommandSpec(
                method="WRITE",
                description="Set servo angle.",
                params={
                    "angle": ParameterSpec(
                        required=True,
                        min=0,
                        max=180,
                        description="Servo angle in degrees.",
                    ),
                },
            )
        ]

    def annotations(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> ToolAnnotations:
        if command.method.strip().upper() != "WRITE":
            raise ValueError(f"Unsupported servo command: {command.method}")
        return ToolAnnotations(
            title=f"Set {connection.name} servo angle",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )

    def build_definitions(self, connection: Connection) -> str:
        return f"Servo {connection.name}_servo;"

    def build_setup_lines(self, connection: Connection) -> list[str]:
        return [f"  {connection.name}_servo.attach({connection.pins['signal']});"]

    def build_handler(self, connection: Connection) -> str:
        return f"""void handle_{connection.name}(const String& input) {{
  String angleValue = parameterValue(input, "angle");

  if (angleValue.length() == 0) {{
    Serial.println("MCP,{connection.event_name},error:invalid_arg");
    return;
  }}

  int angle = angleValue.toInt();
  {connection.name}_servo.write(angle);
  Serial.print("MCP,{connection.event_name},degrees:");
  Serial.println(angle);
}}"""
