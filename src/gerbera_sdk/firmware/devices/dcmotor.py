from mcp.types import ToolAnnotations

from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec
from gerbera_sdk.contracts.firmware_contract import PinMode, PinModeSpec
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.models.hardware.connection import Connection


class DCMotorFirmwareBuilder(BaseFirmwareBuilder):
    def required_libraries(self) -> list:
        return []

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        return [
            PinModeSpec(
                pin=connection.pins["in1"],
                mode=PinMode.OUTPUT,
            ),
            PinModeSpec(
                pin=connection.pins["in2"],
                mode=PinMode.OUTPUT,
            ),
            PinModeSpec(
                pin=connection.pins["enable"],
                mode=PinMode.OUTPUT,
            ),
        ]

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        return [
            CommandSpec(
                method="WRITE",
                description="Set brushed DC motor direction and speed. Use direction 1 for forward, -1 for reverse, and 0 for stop.",
                params={
                    "direction": ParameterSpec(
                        required=True,
                        min=-1,
                        max=1,
                        description="1 drives forward; -1 drives reverse; 0 stops.",
                    ),
                    "speed": ParameterSpec(
                        required=False,
                        min=0,
                        max=255,
                        description="PWM speed from 0 to 255.",
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
            raise ValueError(f"Unsupported DC motor command: {command.method}")
        return ToolAnnotations(
            title=f"Set {connection.name} motor motion",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        )

    def build_handler(self, connection: Connection) -> str:
        in1_pin = connection.pins["in1"]
        in2_pin = connection.pins["in2"]
        enable_pin = connection.pins["enable"]

        return f"""void handle_{connection.name}(const String& input) {{
  String directionValue = parameterValue(input, "direction");
  String speedValue = parameterValue(input, "speed");
  int speed = 255;

  if (directionValue.length() == 0) {{
    Serial.println("MCP,{connection.event_name},error:invalid_arg");
    return;
  }}

  float direction = directionValue.toFloat();

  if (speedValue.length() > 0) {{
    speed = speedValue.toInt();
    if (speed < 0) {{
      speed = 0;
    }}
    if (speed > 255) {{
      speed = 255;
    }}
  }}

  if (direction == 1) {{
    digitalWrite({in1_pin}, HIGH);
    digitalWrite({in2_pin}, LOW);
    analogWrite({enable_pin}, speed);
    Serial.println("MCP,{connection.event_name},status:1");
    return;
  }}

  if (direction == -1) {{
    digitalWrite({in1_pin}, LOW);
    digitalWrite({in2_pin}, HIGH);
    analogWrite({enable_pin}, speed);
    Serial.println("MCP,{connection.event_name},status:-1");
    return;
  }}

  if (direction == 0) {{
    digitalWrite({in1_pin}, LOW);
    digitalWrite({in2_pin}, LOW);
    analogWrite({enable_pin}, 0);
    Serial.println("MCP,{connection.event_name},status:0");
    return;
  }}

  Serial.println("MCP,{connection.event_name},error:invalid_direction");
}}"""
