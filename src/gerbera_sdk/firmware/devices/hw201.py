from gerbera_sdk.contracts.command_contract import CommandSpec
from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.contracts.firmware_contract import PinMode, PinModeSpec
from gerbera_sdk.models.connection import Connection


class HW201FirmwareBuilder(BaseFirmwareBuilder):
    template_name = "hw_201_read"

    def required_libraries(self) -> list:
        return []

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        return [
            PinModeSpec(
                pin=connection.pins["out"],
                mode=PinMode.INPUT,
            )
        ]

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        return [
            CommandSpec(
                method="READ",
                description="Read the current digital sensor value.",
            )
        ]

    def build_handler(self, connection: Connection) -> str:
        out_pin = connection.pins["out"]

        return f"""void handle_{connection.name}(const String& input) {{
  (void)input;
  int value = digitalRead({out_pin});
  Serial.print("value:");
  Serial.println(value);
}}"""
