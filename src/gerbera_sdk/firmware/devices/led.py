from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec, ParameterType
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.contracts.firmware_contract import PinMode, PinModeSpec
from gerbera_sdk.models.connection import Connection


class LEDFirmwareBuilder(BaseFirmwareBuilder):
    template_name = "led_write"

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
                        type=ParameterType.STRING,
                        required=True,
                        enum=["on", "off"],
                        description="Desired LED state.",
                    ),
                },
            )
        ]

    def build_handler(self, connection: Connection) -> str:
        out_pin = connection.pins["out"]

        return f"""void handle_{connection.name}(const String& input) {{
  String value = parameterValue(input, "state");

  if (value.length() == 0) {{
    Serial.println("MCP,{connection.component_type}_{connection.id},error:invalid_arg");
    return;
  }}

  if (value == "on") {{
    digitalWrite({out_pin}, HIGH);
    Serial.println("MCP,{connection.component_type}_{connection.id},state:on");
    return;
  }}

  if (value == "off") {{
    digitalWrite({out_pin}, LOW);
    Serial.println("MCP,{connection.component_type}_{connection.id},state:off");
    return;
  }}

  Serial.println("MCP,{connection.component_type}_{connection.id},error:invalid_value");
}}"""
