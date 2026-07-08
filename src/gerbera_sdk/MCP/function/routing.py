from gerbera_sdk.MCP.function.configurations import BUILDER_MAPPING
from gerbera_sdk.hardware.connection import Connection


class Routing:
    @staticmethod
    def build_setup_code() -> str:
        return """void setup() {
  Serial.begin(BAUD_RATE);
}"""

    @staticmethod
    def build_loop_code(connections: list[Connection]) -> str:
        dispatch_lines = []

        for connection in connections:
            if connection.component_type not in BUILDER_MAPPING:
                raise ValueError(
                    f"Unsupported component type for routing: {connection.component_type}"
                )

            dispatch_lines.append(
                '  if (command.commandName == "%s") {\n'
                "    handle_%s(command);\n"
                "    return;\n"
                "  }"
                % (connection.name, connection.name)
            )

        dispatch_code = "\n".join(dispatch_lines)

        return f"""void loop() {{
  String line = readLine();
  if (line.length() == 0) {{
    return;
  }}

  ParsedCommand command = parseCommand(line);
  if (command.commandName.length() == 0) {{
    return;
  }}

{dispatch_code}
  Serial.println("error:unknown_command");
}}"""
