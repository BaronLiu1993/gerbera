from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.server.commands import CommandCompiler
from gerbera_sdk.models.connection import Connection


class Routing:
    @staticmethod
    def build_setup_code(connections: list[Connection]) -> str:
        setup_lines = [
            "  Serial.begin(BAUD_RATE);",
            "  delay(1000);",
            '  Serial.println("hello");',
        ]
        configured_pins: set[str] = set()

        for connection in connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for routing: {connection.component_type}"
                )

            builder = DEVICES_MAPPING[connection.component_type]()

            for pin_spec in builder.pin_modes(connection):
                if pin_spec.pin in configured_pins:
                    continue

                setup_lines.append(f"  pinMode({pin_spec.pin}, {pin_spec.mode.value});")
                configured_pins.add(pin_spec.pin)

            setup_lines.extend(builder.build_setup_lines(connection))

        setup_body = "\n".join(setup_lines)

        return f"""void setup() {{
{setup_body}
}}"""

    @staticmethod
    def build_loop_code(connections: list[Connection]) -> str:
        dispatch_lines = []

        for connection in connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for routing: {connection.component_type}"
                )

            for command_spec in CommandCompiler.command_specs(connection):
                action = command_spec.method.strip().upper()
                dispatch_lines.append(
                    '    if (action == "%s" && commandName == "%s") {\n'
                    "      handle_%s(line);\n"
                    "      return;\n"
                    "    }"
                    % (action, connection.name, connection.name)
                )

        dispatch_code = "\n".join(dispatch_lines)

        return f"""void loop() {{
  if (Serial.available()) {{
    String line = Serial.readStringUntil('\\n');
    line.trim();
    if (line.length() == 0) {{
      return;
    }}

    String action = actionOf(line);
    String commandName = commandNameOf(line);
    if (action.length() == 0 || commandName.length() == 0) {{
      Serial.println("error:invalid_command");
      return;
    }}

{dispatch_code}
    Serial.print("error:unknown_command:");
    Serial.println(commandName);
  }}
}}"""
