from pathlib import Path
from typing import TYPE_CHECKING

from gerbera_sdk.components.registry import ComponentRegistry
from gerbera_sdk.firmware.builders.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.builders.hw201 import HW201FirmwareBuilder
from gerbera_sdk.hardware.connections import Connection

if TYPE_CHECKING:
    from gerbera_sdk.hardware.microcontroller import Microcontroller


class FirmwareGenerator:
    _builders: dict[str, BaseFirmwareBuilder] = {
        HW201FirmwareBuilder.template_name: HW201FirmwareBuilder(),
    }

    @staticmethod
    def generate(microcontroller: "Microcontroller") -> str:
        handlers = "\n\n".join(
            FirmwareGenerator._build_handler(connection)
            for connection in microcontroller.connections
        )
        dispatch_lines = "\n".join(
            FirmwareGenerator._build_dispatch_line(connection.name)
            for connection in microcontroller.connections
        )

        return f"""const int BAUD_RATE = {microcontroller.baud_rate};

String readLine() {{
  if (!Serial.available()) {{
    return "";
  }}

  return Serial.readStringUntil('\\n');
}}

String firstToken(String input) {{
  int firstComma = input.indexOf(',');
  if (firstComma == -1) {{
    return input;
  }}

  return input.substring(0, firstComma);
}}

String parameterValue(String input, String parameterName) {{
  int start = 0;

  while (start < input.length()) {{
    int commaIndex = input.indexOf(',', start);
    String token;

    if (commaIndex == -1) {{
      token = input.substring(start);
      start = input.length();
    }} else {{
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }}

    int firstColon = token.indexOf(':');
    int secondColon = token.indexOf(':', firstColon + 1);

    if (firstColon == -1 || secondColon == -1) {{
      continue;
    }}

    String tokenName = token.substring(0, firstColon);
    if (tokenName != parameterName) {{
      continue;
    }}

    return token.substring(secondColon + 1);
  }}

  return "";
}}

void setup() {{
  Serial.begin(BAUD_RATE);
}}

void loop() {{
  String line = readLine();
  if (line.length() == 0) {{
    return;
  }}

  line.trim();
  String commandName = firstToken(line);
{dispatch_lines}
  Serial.println("error:unknown_command");
}}

{handlers}
"""

    @staticmethod
    def write_sketch(microcontroller: "Microcontroller", sketch_root: Path) -> Path:
        sketch_root.mkdir(parents=True, exist_ok=True)
        sketch_path = sketch_root / f"{microcontroller.id}.ino"
        sketch_path.write_text(FirmwareGenerator.generate(microcontroller))
        return sketch_path

    @staticmethod
    def _build_dispatch_line(connection_name: str) -> str:
        return (
            f'  if (commandName == "{connection_name}") {{\n'
            f"    handle_{connection_name}();\n"
            f"    return;\n"
            f"  }}"
        )

    @staticmethod
    def _build_handler(connection: Connection) -> str:
        profile = ComponentRegistry.get(connection.component_type)
        template_name = profile["template"]

        if template_name not in FirmwareGenerator._builders:
            raise ValueError(f"Unsupported firmware template: {template_name}")

        return FirmwareGenerator._builders[template_name].build_handler(connection)
