from mcp.types import ToolAnnotations

from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.contracts.firmware_contract import PinMode, PinModeSpec
from gerbera_sdk.models.hardware.connection import Connection


class LEDFirmwareBuilder(BaseFirmwareBuilder):
    def required_libraries(self) -> list:
        return []

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        return [
            PinModeSpec(
                pin=connection.pins["out"],
                mode=PinMode.OUTPUT,
            )
        ]

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        return [
            CommandSpec(
                method="WRITE",
                description="Set the LED state.",
                params={
                    "state": ParameterSpec(
                        required=True,
                        min=0,
                        max=1,
                        description="1 turns the LED on; 0 turns it off.",
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
            raise ValueError(f"Unsupported LED command: {command.method}")
        return ToolAnnotations(
            title=f"Set {connection.name} LED state",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )

    def build_handler(self, connection: Connection) -> str:
        out_pin = connection.pins["out"]

        return f"""void handle_{connection.name}(const String& input) {{
  String stateValue = parameterValue(input, "state");

  if (stateValue.length() == 0) {{
    Serial.println("MCP,{connection.event_name},error:invalid_arg");
    return;
  }}

  float state = stateValue.toFloat();

  if (state == 1) {{
    digitalWrite({out_pin}, HIGH);
    Serial.println("MCP,{connection.event_name},state:1");
    return;
  }}

  if (state == 0) {{
    digitalWrite({out_pin}, LOW);
    Serial.println("MCP,{connection.event_name},state:0");
    return;
  }}

  Serial.println("MCP,{connection.event_name},error:invalid_state");
}}"""
