from gerbera_sdk.firmware.function.devices.base import BaseFirmwareBuilder
from gerbera_sdk.models.connection import Connection


class HW201FirmwareBuilder(BaseFirmwareBuilder):
    template_name = "hw_201_read"

    def required_libraries(self) -> list[dict[str, str]]:
        return []

    def pin_modes(self, connection: Connection) -> dict[str, str]:
        return {
            connection.pins["out"]: "INPUT",
        }

    def required_commands(self, connection: Connection) -> list[str]:
        return [f"READ,{connection.name}"]

    def build_handler(self, connection: Connection) -> str:
        out_pin = connection.pins["out"]

        return f"""void handle_{connection.name}(const String& rawArg) {{
  (void)rawArg;
  int value = digitalRead({out_pin});
  Serial.print("value:");
  Serial.println(value);
}}"""
