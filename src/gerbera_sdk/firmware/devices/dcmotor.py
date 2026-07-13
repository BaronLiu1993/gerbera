from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec, ParameterType
from gerbera_sdk.contracts.firmware_contract import PinMode, PinModeSpec
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.models.connection import Connection


class DCMotorFirmwareBuilder(BaseFirmwareBuilder):
    template_name = "dcmotor_write"

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
        _ = connection
        return [
            CommandSpec(
                method="WRITE",
                description="Set brushed DC motor direction and speed.",
                params={
                    "direction": ParameterSpec(
                        type=ParameterType.STRING,
                        required=True,
                        enum=["forward", "reverse", "stop"],
                        description="Motor direction.",
                    ),
                    "speed": ParameterSpec(
                        type=ParameterType.INT,
                        required=False,
                        min=0,
                        max=255,
                        description="PWM speed from 0 to 255.",
                    ),
                },
            )
        ]

    def build_handler(self, connection: Connection) -> str:
        in1_pin = connection.pins["in1"]
        in2_pin = connection.pins["in2"]
        enable_pin = connection.pins["enable"]

        return f"""void handle_{connection.name}(const String& input) {{
  String direction = parameterValue(input, "direction");
  String speedValue = parameterValue(input, "speed");
  int speed = 255;

  if (direction.length() == 0) {{
    Serial.println("MCP,{connection.event_name},error:invalid_arg");
    return;
  }}

  if (speedValue.length() > 0) {{
    speed = speedValue.toInt();
    if (speed < 0) {{
      speed = 0;
    }}
    if (speed > 255) {{
      speed = 255;
    }}
  }}

  if (direction == "forward") {{
    digitalWrite({in1_pin}, HIGH);
    digitalWrite({in2_pin}, LOW);
    analogWrite({enable_pin}, speed);
    Serial.println("MCP,{connection.event_name},status:forward");
    return;
  }}

  if (direction == "reverse") {{
    digitalWrite({in1_pin}, LOW);
    digitalWrite({in2_pin}, HIGH);
    analogWrite({enable_pin}, speed);
    Serial.println("MCP,{connection.event_name},status:reverse");
    return;
  }}

  if (direction == "stop") {{
    digitalWrite({in1_pin}, LOW);
    digitalWrite({in2_pin}, LOW);
    analogWrite({enable_pin}, 0);
    Serial.println("MCP,{connection.event_name},status:stop");
    return;
  }}

  Serial.println("MCP,{connection.event_name},error:invalid_direction");
}}"""
