from gerbera_sdk.firmware.function.devices.base import BaseFirmwareBuilder
from gerbera_sdk.models.connection import Connection

class HW201FirmwareBuilder(BaseFirmwareBuilder):
    template_name = "hw_201_read"

    # Each entry should declare the Arduino library install name and the
    # corresponding #include import name used in generated firmware. 
    # So key is the library install name and the value is the import name
    def required_libraries(self) -> list[dict[str, str]]:
        return []
    
    def required_commands(self, connection) -> list[str]:
        return [f"READ,{connection.name}"]

    def build_handler(self, connection: Connection) -> str:
        out_pin = connection.pins["out"]

        return f"""void handle_{connection.name}(const ParsedCommand& command) {{
  if (command.action != "READ") {{
    Serial.println("error:invalid_action");
    return;
  }}

  int value = digitalRead({out_pin});

  Serial.print("value:");
  Serial.println(value);
}}"""
