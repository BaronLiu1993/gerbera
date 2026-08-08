from dataclasses import dataclass

from gerbera_sdk.firmware.configurations import (
    MICROCONTROLLER_MAPPING,
    get_device_builder,
)
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


@dataclass(frozen=True)
class FirmwareGenerator:
    microcontroller: Microcontroller

    def build(self) -> str:
        return f"""{self.includes()}

const long BAUD_RATE = {self.microcontroller.baud_rate};

{self.parser_code()}

{self.definitions()}

{self.handlers()}

{self.setup_code()}

{self.loop_code()}
"""

    @classmethod
    def build_firmware(cls, microcontroller: Microcontroller) -> str:
        return cls(microcontroller).build()

    @classmethod
    def build_setup_code(cls, connections: list[Connection]) -> str:
        return cls._setup_code(connections)

    @classmethod
    def build_loop_code(cls, connections: list[Connection]) -> str:
        return cls._loop_code(connections)

    def includes(self) -> str:
        includes: list[str] = []
        seen: set[str] = set()

        board_config = MICROCONTROLLER_MAPPING.get(
            self.microcontroller.fqbn,
            {"includes": ["Arduino.h"]},
        )
        for include_name in board_config["includes"]:
            self._append_include(includes, seen, include_name)

        for connection in self.microcontroller.connections:
            builder = get_device_builder(connection.component_type)
            for library in builder.required_libraries():
                self._append_include(includes, seen, library.include)

        return "\n".join(includes)

    def definitions(self) -> str:
        definitions = []

        for connection in self.microcontroller.connections:
            builder = get_device_builder(connection.component_type)
            definition = builder.build_definitions(connection).strip()
            if definition:
                definitions.append(definition)

        return "\n\n".join(definitions)

    def handlers(self) -> str:
        handlers = []

        for connection in self.microcontroller.connections:
            builder = get_device_builder(connection.component_type)
            handlers.append(builder.build_handler(connection))

        return "\n\n".join(handlers)

    def setup_code(self) -> str:
        return self._setup_code(self.microcontroller.connections)

    def loop_code(self) -> str:
        return self._loop_code(self.microcontroller.connections)

    @staticmethod
    def _setup_code(connections: list[Connection]) -> str:
        setup_lines = [
            "  Serial.begin(BAUD_RATE);",
            "  delay(1000);",
            '  Serial.println("hello");',
        ]
        configured_pins: set[str] = set()

        for connection in connections:
            builder = get_device_builder(connection.component_type)

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
    def _loop_code(connections: list[Connection]) -> str:
        stream_lines = []
        dispatch_lines = []

        for connection in connections:
            builder = get_device_builder(connection.component_type)
            stream_lines.extend(builder.build_stream_lines(connection))
            dispatch_lines.extend(FirmwareGenerator._dispatch_lines(connection))

        stream_code = "\n".join(stream_lines)
        dispatch_code = "\n".join(dispatch_lines)
        return f"""void loop() {{
{stream_code}
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

    @staticmethod
    def parser_code() -> str:
        return """String tokenAt(String input, int tokenIndex) {
  int start = 0;
  int currentIndex = 0;

  while (start <= input.length()) {
    int commaIndex = input.indexOf(',', start);
    String token;

    if (commaIndex == -1) {
      token = input.substring(start);
      start = input.length() + 1;
    } else {
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }

    token.trim();
    if (currentIndex == tokenIndex) {
      return token;
    }

    currentIndex++;
  }

  return "";
}

String actionOf(String input) {
  return tokenAt(input, 0);
}

String commandNameOf(String input) {
  return tokenAt(input, 1);
}

String rawArgOf(String input) {
  return tokenAt(input, 2);
}

String parameterValue(String input, String parameterName) {
  int start = 0;
  int currentIndex = 0;

  while (start <= input.length()) {
    int commaIndex = input.indexOf(',', start);
    String token;

    if (commaIndex == -1) {
      token = input.substring(start);
      start = input.length() + 1;
    } else {
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }

    token.trim();
    if (currentIndex < 2) {
      currentIndex++;
      continue;
    }

    int colonIndex = token.indexOf(':');
    if (colonIndex == -1) {
      currentIndex++;
      continue;
    }

    String key = token.substring(0, colonIndex);
    key.trim();
    if (key == parameterName) {
      String value = token.substring(colonIndex + 1);
      value.trim();
      return value;
    }

    currentIndex++;
  }

  return "";
}"""

    @staticmethod
    def _append_include(
        includes: list[str],
        seen: set[str],
        include_name: str,
    ) -> None:
        if not include_name:
            return

        include = f"#include <{include_name}>"
        key = include.strip().lower()
        if key in seen:
            return

        includes.append(include)
        seen.add(key)

    @staticmethod
    def _dispatch_lines(connection: Connection) -> list[str]:
        lines = []
        for command_spec in CommandCompiler.command_specs(connection):
            action = command_spec.method.strip().upper()
            lines.append(
                '    if (action == "%s" && commandName == "%s") {\n'
                "      handle_%s(line);\n"
                "      return;\n"
                "    }"
                % (action, connection.name, connection.name)
            )
        return lines
