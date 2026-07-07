from gerbera_sdk.MCP.function.base import BaseFirmwareBuilder
from gerbera_sdk.hardware.connection import Connection


class HW201FirmwareBuilder(BaseFirmwareBuilder):
    template_name = "hw_201_read"
    
    def build_handler(self, connection: Connection) -> str:
        signal_pin = connection.pins["signal"]

        return f"""void handle_{connection.name}(const ParsedCommand& command) {{
  if (command.action != "READ") {{
    Serial.println("error:invalid_action");
    return;
  }}

  int raw = analogRead({signal_pin});
  float voltage = raw * (5.0 / 1023.0);
  float celsius = (voltage - 0.5) * 100.0;

  Serial.print("value:");
  Serial.print(celsius);
  Serial.println(",unit:celsius");
}}"""
