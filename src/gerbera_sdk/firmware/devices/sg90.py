from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec, ParameterType
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.contracts.firmware_contract import LibrarySpec, PinModeSpec
from gerbera_sdk.models.connection import Connection


class SG90FirmwareBuilder(BaseFirmwareBuilder):
    template_name = "sg90_write"

    def required_libraries(self) -> list[LibrarySpec]:
        return [
            LibrarySpec(
                include="Servo.h",
                install="Servo",
            )
        ]

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        _ = connection
        return []

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        _ = connection
        return [
            CommandSpec(
                method="WRITE",
                description="Set servo angle.",
                params={
                    "angle": ParameterSpec(
                        type=ParameterType.INT,
                        required=True,
                        min=0,
                        max=180,
                        description="Servo angle in degrees.",
                    ),
                },
            )
        ]

    def build_definitions(self, connection: Connection) -> str:
        return f"Servo {connection.name}_servo;"

    def build_setup_lines(self, connection: Connection) -> list[str]:
        return [f"  {connection.name}_servo.attach({connection.pins['signal']});"]

    def build_handler(self, connection: Connection) -> str:
        return f"""void handle_{connection.name}(const String& input) {{
  String angleValue = parameterValue(input, "angle");

  if (angleValue.length() == 0) {{
    Serial.println("MCP,{connection.component_type}_{connection.id},error:invalid_arg");
    return;
  }}

  int angle = angleValue.toInt();
  {connection.name}_servo.write(angle);
  Serial.print("MCP,{connection.component_type}_{connection.id},angle:");
  Serial.println(angle);
}}"""
