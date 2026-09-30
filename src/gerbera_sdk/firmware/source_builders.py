from dataclasses import dataclass
import json

from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.firmware.firmware_schema import (
    BoardTransportKind,
    GERBERA_CHECK,
    GERBERA_HANDSHAKE,
    GERBERA_HANDSHAKE_TARGET,
    GERBERA_HEARTBEAT,
    GERBERA_PROTOCOL_VERSION,
    GERBERA_START,
    GERBERA_STATE_CHECKING,
    GERBERA_STATE_READY,
    GERBERA_STATE_STOPPED,
    GERBERA_STOP,
    MAX_SERIAL_MESSAGE_BYTES,
)
from gerbera_sdk.models.hardware.hardware_plan import (
    ResolvedBoard,
    ResolvedConnection,
)
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


@dataclass(frozen=True)
class RuntimeSourceBuilder:
    board: ResolvedBoard

    def build_sketch(self) -> str:
        return """#include \"GerberaRuntime.h\"

GerberaRuntime runtime;

void setup() {
  runtime.setup();
}

void loop() {
  runtime.update();
}
"""

    def build_header(self) -> str:
        return f"""#pragma once

#include <Arduino.h>
{self.transport_header()}

enum RuntimeState {{
  {GERBERA_STATE_CHECKING},
  {GERBERA_STATE_READY},
  {GERBERA_STATE_STOPPED}
}};

class GerberaRuntime {{
 public:
  void setup();
  void update();
  bool isReady() const;

 private:
  RuntimeState state = {GERBERA_STATE_CHECKING};
  String activeSession;
  String stopReason;
  String stoppedComponent;
  unsigned long lastHeartbeatAt = 0;

  void processSerialMessage();
  void handleHandshake(const String& input);
  void handleComponentCheck(const String& input);
  void handleStart(const String& input);
  void handleHeartbeat(const String& input);
  void handleStop(const String& input);
  void checkHeartbeatDeadline();
  void monitorComponents();
  void enterStoppedState(const String& reason, const String& component);
}};
"""

    def build_source(self) -> str:
        return f"""#include \"GerberaRuntime.h\"

#include \"Components.h\"
#include \"DeviceCommands.h\"

{self.transport_definition()}
const long BAUD_RATE = {self.board.baud_rate};
const unsigned long HEARTBEAT_TIMEOUT_MS = {self.board.watchdog.heartbeat_timeout_ms};
const unsigned int MAX_SERIAL_MESSAGE_LENGTH = {MAX_SERIAL_MESSAGE_BYTES};
const char* GERBERA_BOARD_ID = {json.dumps(self.board.microcontroller_id)};
const char* GERBERA_CONTRACT_DIGEST = {json.dumps(self.board.contract_digest)};

void GerberaRuntime::setup() {{
  {self.transport_setup()}
  setupComponentPins();
  setupDeviceCommands();
  stopAllComponents();
  state = {GERBERA_STATE_CHECKING};
  activeSession = "";
  stopReason = "";
  stoppedComponent = "";
  resetComponentChecks();
}}

void GerberaRuntime::update() {{
  checkHeartbeatDeadline();
  monitorComponents();
  updateDeviceStreams(*this);
  processSerialMessage();
  checkHeartbeatDeadline();
  monitorComponents();
}}

bool GerberaRuntime::isReady() const {{
  return state == {GERBERA_STATE_READY};
}}

void GerberaRuntime::processSerialMessage() {{
  if (!GERBERA_TRANSPORT.available()) {{
    return;
  }}
  String input = GERBERA_TRANSPORT.readStringUntil('\\n');
  input.trim();
  if (input.length() > MAX_SERIAL_MESSAGE_LENGTH) {{
    GERBERA_TRANSPORT.println("error:message_too_large");
    return;
  }}
  if (input.length() == 0) {{
    return;
  }}

  String action = actionOf(input);
  String target = commandNameOf(input);
  if (action == "{GERBERA_HANDSHAKE}" && target == "{GERBERA_HANDSHAKE_TARGET}") {{
    handleHandshake(input);
    return;
  }}
  if (action == "{GERBERA_CHECK}") {{
    handleComponentCheck(input);
    return;
  }}
  if (action == "{GERBERA_START}" && target == "{GERBERA_HANDSHAKE_TARGET}") {{
    handleStart(input);
    return;
  }}
  if (action == "{GERBERA_HEARTBEAT}" && target == "{GERBERA_HANDSHAKE_TARGET}") {{
    handleHeartbeat(input);
    return;
  }}
  if (action == "{GERBERA_STOP}" && target == "{GERBERA_HANDSHAKE_TARGET}") {{
    handleStop(input);
    return;
  }}
  dispatchDeviceCommand(*this, input);
}}

void GerberaRuntime::handleHandshake(const String& input) {{
  if (tokenCount(input) != 3 || !tokenAt(input, 2).startsWith("challenge:")) {{
    GERBERA_TRANSPORT.println("{GERBERA_HANDSHAKE},{GERBERA_HANDSHAKE_TARGET},error:invalid_fields");
    return;
  }}
  String challenge = parameterValue(input, "challenge");
  if (challenge.length() == 0) {{
    GERBERA_TRANSPORT.println("{GERBERA_HANDSHAKE},{GERBERA_HANDSHAKE_TARGET},error:missing_challenge");
    return;
  }}

  stopAllComponents();
  state = {GERBERA_STATE_CHECKING};
  activeSession = challenge;
  stopReason = "";
  stoppedComponent = "";
  resetComponentChecks();
  GERBERA_TRANSPORT.print("{GERBERA_HANDSHAKE},{GERBERA_HANDSHAKE_TARGET},protocol:{GERBERA_PROTOCOL_VERSION}");
  GERBERA_TRANSPORT.print(",board:");
  GERBERA_TRANSPORT.print(GERBERA_BOARD_ID);
  GERBERA_TRANSPORT.print(",digest:");
  GERBERA_TRANSPORT.print(GERBERA_CONTRACT_DIGEST);
  GERBERA_TRANSPORT.print(",challenge:");
  GERBERA_TRANSPORT.println(challenge);
}}

void GerberaRuntime::handleComponentCheck(const String& input) {{
  String componentKey = commandNameOf(input);
  String session = parameterValue(input, "session");
  if (state != {GERBERA_STATE_CHECKING} || tokenCount(input) != 3 || session != activeSession) {{
    enterStoppedState("invalid_session", componentKey);
    return;
  }}
  ComponentMonitor* component = findComponent(componentKey);
  if (component == nullptr || !runComponentCheck(*component)) {{
    enterStoppedState("component_check_failed", componentKey);
    GERBERA_TRANSPORT.print("{GERBERA_CHECK},");
    GERBERA_TRANSPORT.print(componentKey);
    GERBERA_TRANSPORT.print(",status:fail,error:component_check_failed,session:");
    GERBERA_TRANSPORT.println(activeSession);
    return;
  }}
  component->checkPassed = true;
  GERBERA_TRANSPORT.print("{GERBERA_CHECK},");
  GERBERA_TRANSPORT.print(componentKey);
  GERBERA_TRANSPORT.print(",status:pass,session:");
  GERBERA_TRANSPORT.println(activeSession);
}}

void GerberaRuntime::handleStart(const String& input) {{
  String session = parameterValue(input, "session");
  if (state != {GERBERA_STATE_CHECKING} || tokenCount(input) != 3 || session != activeSession) {{
    enterStoppedState("invalid_session", "{GERBERA_HANDSHAKE_TARGET}");
    return;
  }}
  if (!allComponentsChecked()) {{
    enterStoppedState("component_check_failed", "{GERBERA_HANDSHAKE_TARGET}");
    return;
  }}
  state = {GERBERA_STATE_READY};
  lastHeartbeatAt = millis();
  resetComponentMonitorTimes(lastHeartbeatAt);
  GERBERA_TRANSPORT.print("{GERBERA_START},{GERBERA_HANDSHAKE_TARGET},state:{GERBERA_STATE_READY},session:");
  GERBERA_TRANSPORT.println(activeSession);
}}

void GerberaRuntime::handleHeartbeat(const String& input) {{
  String session = parameterValue(input, "session");
  String sequence = parameterValue(input, "sequence");
  if (state != {GERBERA_STATE_READY} || tokenCount(input) != 4 || session != activeSession ||
      sequence.length() == 0 || !isUnsignedInteger(sequence)) {{
    if (state == {GERBERA_STATE_READY}) {{
      enterStoppedState("invalid_session", "{GERBERA_HANDSHAKE_TARGET}");
    }}
    return;
  }}
  lastHeartbeatAt = millis();
}}

void GerberaRuntime::handleStop(const String& input) {{
  String session = parameterValue(input, "session");
  if (tokenCount(input) != 3 || session != activeSession) {{
    enterStoppedState("invalid_session", "{GERBERA_HANDSHAKE_TARGET}");
    return;
  }}
  enterStoppedState("operator_stop", "{GERBERA_HANDSHAKE_TARGET}");
}}

void GerberaRuntime::checkHeartbeatDeadline() {{
  if (state != {GERBERA_STATE_READY}) {{
    return;
  }}
  if (millis() - lastHeartbeatAt > HEARTBEAT_TIMEOUT_MS) {{
    enterStoppedState("heartbeat_timeout", "{GERBERA_HANDSHAKE_TARGET}");
  }}
}}

void GerberaRuntime::monitorComponents() {{
  if (state != {GERBERA_STATE_READY}) {{
    return;
  }}
  unsigned long now = millis();
  for (size_t index = 0; index < componentCount; index++) {{
    ComponentMonitor& component = components[index];
    if (now - component.lastMonitorAt < component.monitorIntervalMs) {{
      continue;
    }}
    component.lastMonitorAt = now;
    if (!component.monitor()) {{
      enterStoppedState("component_feedback_lost", component.key);
      return;
    }}
  }}
}}

void GerberaRuntime::enterStoppedState(
    const String& reason,
    const String& component
) {{
  stopAllComponents();
  if (state == {GERBERA_STATE_STOPPED}) {{
    return;
  }}
  state = {GERBERA_STATE_STOPPED};
  stopReason = reason;
  stoppedComponent = component;
}}
"""

    def transport_header(self) -> str:
        if (
            self.board.active_runtime_transport.kind
            == BoardTransportKind.BLUETOOTH_CLASSIC
        ):
            return (
                "#include <BluetoothSerial.h>\n\n"
                "extern BluetoothSerial GERBERA_TRANSPORT;"
            )
        return "#define GERBERA_TRANSPORT Serial"

    def transport_definition(self) -> str:
        if (
            self.board.active_runtime_transport.kind
            == BoardTransportKind.BLUETOOTH_CLASSIC
        ):
            return "BluetoothSerial GERBERA_TRANSPORT;"
        return ""

    def transport_setup(self) -> str:
        transport = self.board.active_runtime_transport
        if transport.kind == BoardTransportKind.BLUETOOTH_CLASSIC:
            return (
                "GERBERA_TRANSPORT.begin("
                f"{json.dumps(transport.device_name)});"
            )
        return "GERBERA_TRANSPORT.begin(BAUD_RATE);"


@dataclass(frozen=True)
class ComponentSourceBuilder:
    board: ResolvedBoard

    def build_header(self) -> str:
        return f"""#pragma once

#include <Arduino.h>
{self.library_includes()}

struct ComponentMonitor {{
  const char* key;
  bool (*check)();
  bool (*monitor)();
  void (*stop)();
  unsigned long startupTimeoutMs;
  unsigned long monitorIntervalMs;
  unsigned long lastMonitorAt;
  bool checkPassed;
}};

{self.definition_declarations()}

extern ComponentMonitor components[];
extern const size_t componentCount;

void setupComponentPins();
void resetComponentChecks();
void resetComponentMonitorTimes(unsigned long now);
void stopAllComponents();
ComponentMonitor* findComponent(const String& key);
bool runComponentCheck(ComponentMonitor& component);
bool allComponentsChecked();
"""

    def build_source(self) -> str:
        strategies = "\n\n".join(
            self.connection_strategies(connection)
            for connection in self.board.connections
        )
        return f"""#include \"Components.h\"

{self.device_definitions()}

{strategies}

{self.component_registry()}

void setupComponentPins() {{
{self.setup_lines()}
}}

void resetComponentChecks() {{
  for (size_t index = 0; index < componentCount; index++) {{
    components[index].checkPassed = false;
  }}
}}

void resetComponentMonitorTimes(unsigned long now) {{
  for (size_t index = 0; index < componentCount; index++) {{
    components[index].lastMonitorAt = now;
  }}
}}

void stopAllComponents() {{
  for (size_t index = 0; index < componentCount; index++) {{
    components[index].stop();
  }}
}}

ComponentMonitor* findComponent(const String& key) {{
  for (size_t index = 0; index < componentCount; index++) {{
    if (key == components[index].key) {{
      return &components[index];
    }}
  }}
  return nullptr;
}}

bool runComponentCheck(ComponentMonitor& component) {{
  unsigned long startedAt = millis();
  bool passed = component.check();
  return passed && millis() - startedAt <= component.startupTimeoutMs;
}}

bool allComponentsChecked() {{
  for (size_t index = 0; index < componentCount; index++) {{
    if (!components[index].checkPassed) {{
      return false;
    }}
  }}
  return true;
}}
"""

    def library_includes(self) -> str:
        includes: list[str] = []
        seen: set[str] = set()
        for include_name in self.board.definition.includes:
            self.append_include(includes, seen, include_name)
        for connection in self.board.connections:
            for library in get_device_builder(
                connection.component_type
            ).required_libraries():
                self.append_include(includes, seen, library.include)
        return "\n".join(includes)

    def device_definitions(self) -> str:
        definitions: list[str] = []
        for connection in self.board.connections:
            definition = get_device_builder(
                connection.component_type
            ).build_definitions(connection).strip()
            if definition:
                definitions.append(definition)
        return "\n\n".join(definitions)

    def definition_declarations(self) -> str:
        declarations: list[str] = []
        for line in self.device_definitions().splitlines():
            stripped = line.strip()
            if not stripped or not stripped.endswith(";"):
                continue
            left_side = stripped[:-1].split("=", 1)[0].strip()
            if " " in left_side:
                declarations.append(f"extern {left_side};")
        return "\n".join(declarations)

    def connection_strategies(self, connection: ResolvedConnection) -> str:
        builder = get_device_builder(connection.component_type)
        verification = connection.verification
        check = builder.render(verification.check, connection).strip()
        monitor = builder.render(verification.monitor, connection).strip()
        safe_stop = builder.render(verification.safe_stop, connection).strip()
        return f"""bool check_{connection.name}() {{
{self.indent(check)}
}}

bool monitor_{connection.name}() {{
{self.indent(monitor)}
}}

void stop_{connection.name}() {{
{self.indent(safe_stop)}
}}"""

    def component_registry(self) -> str:
        if not self.board.connections:
            return (
                "ComponentMonitor components[1] = {};\n"
                "const size_t componentCount = 0;"
            )
        entries = []
        for connection in self.board.connections:
            verification = connection.verification
            key = f"{self.board.microcontroller_id}.{connection.name}"
            entries.append(
                "  {"
                f"{json.dumps(key)}, check_{connection.name}, "
                f"monitor_{connection.name}, stop_{connection.name}, "
                f"{verification.startup_timeout_ms}, "
                f"{verification.monitor_interval_ms}, 0, false"
                "}"
            )
        return (
            "ComponentMonitor components[] = {\n"
            + ",\n".join(entries)
            + "\n};\nconst size_t componentCount = "
            "sizeof(components) / sizeof(components[0]);"
        )

    def setup_lines(self) -> str:
        lines: list[str] = []
        configured_pins: set[str] = set()
        for connection in self.board.connections:
            builder = get_device_builder(connection.component_type)
            for pin_spec in builder.pin_modes(connection):
                if pin_spec.pin in configured_pins:
                    raise ValueError(
                        "Firmware attempted to configure physical pin twice: "
                        f"{pin_spec.pin}"
                    )
                lines.append(f"  pinMode({pin_spec.pin}, {pin_spec.mode.value});")
                configured_pins.add(pin_spec.pin)
        return "\n".join(lines)

    @staticmethod
    def append_include(
        includes: list[str],
        seen: set[str],
        include_name: str,
    ) -> None:
        if not include_name:
            return
        include = f"#include <{include_name}>"
        normalized = include.casefold()
        if normalized not in seen:
            includes.append(include)
            seen.add(normalized)

    @staticmethod
    def indent(block: str) -> str:
        if not block:
            return "  (void)0;"
        return "\n".join(f"  {line}" for line in block.splitlines())


@dataclass(frozen=True)
class DeviceCommandSourceBuilder:
    board: ResolvedBoard

    def build_header(self) -> str:
        return """#pragma once

#include <Arduino.h>

class GerberaRuntime;

String tokenAt(const String& input, int tokenIndex);
int tokenCount(const String& input);
String actionOf(const String& input);
String commandNameOf(const String& input);
String parameterValue(const String& input, const String& parameterName);
bool isUnsignedInteger(const String& value);
void setupDeviceCommands();
void updateDeviceStreams(const GerberaRuntime& runtime);
void dispatchDeviceCommand(GerberaRuntime& runtime, const String& input);
"""

    def build_source(self) -> str:
        handlers = "\n\n".join(
            get_device_builder(connection.component_type).build_handler(
                connection
            )
            for connection in self.board.connections
        )
        return f"""#include \"DeviceCommands.h\"

#include \"Components.h\"
#include \"GerberaRuntime.h\"

String tokenAt(const String& input, int tokenIndex) {{
  int start = 0;
  int currentIndex = 0;
  while (start <= input.length()) {{
    int commaIndex = input.indexOf(',', start);
    String token;
    if (commaIndex == -1) {{
      token = input.substring(start);
      start = input.length() + 1;
    }} else {{
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }}
    token.trim();
    if (currentIndex == tokenIndex) {{
      return token;
    }}
    currentIndex++;
  }}
  return "";
}}

int tokenCount(const String& input) {{
  if (input.length() == 0) {{
    return 0;
  }}
  int count = 1;
  for (unsigned int index = 0; index < input.length(); index++) {{
    if (input.charAt(index) == ',') {{
      count++;
    }}
  }}
  return count;
}}

String actionOf(const String& input) {{
  return tokenAt(input, 0);
}}

String commandNameOf(const String& input) {{
  return tokenAt(input, 1);
}}

String parameterValue(const String& input, const String& parameterName) {{
  for (int index = 2; index < tokenCount(input); index++) {{
    String token = tokenAt(input, index);
    int colonIndex = token.indexOf(':');
    if (colonIndex == -1) {{
      continue;
    }}
    String key = token.substring(0, colonIndex);
    key.trim();
    if (key == parameterName) {{
      String value = token.substring(colonIndex + 1);
      value.trim();
      return value;
    }}
  }}
  return "";
}}

bool isUnsignedInteger(const String& value) {{
  for (unsigned int index = 0; index < value.length(); index++) {{
    if (!isDigit(value.charAt(index))) {{
      return false;
    }}
  }}
  return value.length() > 0;
}}

{handlers}

void setupDeviceCommands() {{
{self.setup_lines()}
}}

void updateDeviceStreams(const GerberaRuntime& runtime) {{
  if (!runtime.isReady()) {{
    return;
  }}
{self.stream_lines()}
}}

void dispatchDeviceCommand(GerberaRuntime& runtime, const String& input) {{
  if (!runtime.isReady()) {{
    GERBERA_TRANSPORT.println("error:hardware_not_ready");
    return;
  }}
  String action = actionOf(input);
  String commandName = commandNameOf(input);
  if (action.length() == 0 || commandName.length() == 0) {{
    GERBERA_TRANSPORT.println("error:invalid_command");
    return;
  }}
{self.dispatch_lines()}
  GERBERA_TRANSPORT.print("error:unknown_command:");
  GERBERA_TRANSPORT.println(commandName);
}}
"""

    def setup_lines(self) -> str:
        lines: list[str] = []
        for connection in self.board.connections:
            lines.extend(
                get_device_builder(
                    connection.component_type
                ).build_setup_lines(connection)
            )
        return "\n".join(lines)

    def stream_lines(self) -> str:
        lines: list[str] = []
        for connection in self.board.connections:
            lines.extend(
                get_device_builder(
                    connection.component_type
                ).build_stream_lines(connection)
            )
        return "\n".join(lines)

    def dispatch_lines(self) -> str:
        lines: list[str] = []
        for connection in self.board.connections:
            for command_spec in CommandCompiler.command_specs(connection):
                action = command_spec.method.strip().upper()
                lines.extend(
                    (
                        f'  if (action == "{action}" && commandName == '
                        f'"{connection.name}") {{',
                        f"    handle_{connection.name}(input);",
                        "    return;",
                        "  }",
                    )
                )
        return "\n".join(lines)
