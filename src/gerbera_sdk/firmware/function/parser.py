# Generate Parsed Script
class Parser:
    @staticmethod
    def parse_command_code() -> str:
        return """struct Param {
  String key;
  String value;
};

struct ParsedCommand {
  String action;
  String commandName;
  Param params[8];
  int paramCount;
};

String readLine() {
  if (!Serial.available()) {
    return "";
  }

  return Serial.readStringUntil('\\n');
}

String tokenAt(String input, int tokenIndex) {
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

ParsedCommand parseCommand(String input) {
  ParsedCommand command;
  command.action = "";
  command.commandName = "";
  command.paramCount = 0;

  input.trim();
  if (input.length() == 0) {
    return command;
  }

  command.action = actionOf(input);
  command.commandName = commandNameOf(input);

  int start = 0;
  int currentIndex = 0;

  while (start <= input.length() && command.paramCount < 8) {
    int commaIndex = input.indexOf(',', start);
    String token;

    if (commaIndex == -1) {
      token = input.substring(start);
      start = input.length() + 1;
    } else {
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }

    if (currentIndex < 2) {
      currentIndex++;
      continue;
    }

    token.trim();
    if (token.length() == 0) {
      currentIndex++;
      continue;
    }

    int colonIndex = token.indexOf(':');
    if (colonIndex == -1) {
      currentIndex++;
      continue;
    }

    command.params[command.paramCount].key = token.substring(0, colonIndex);
    command.params[command.paramCount].value = token.substring(colonIndex + 1);
    command.paramCount++;

    currentIndex++;
  }

  return command;
}

String getParam(const ParsedCommand& command, String parameterName) {
  if (command.paramCount == 0) {
    return "";
  }

  for (int i = 0; i < command.paramCount; i++) {
    if (command.params[i].key == parameterName) {
      return command.params[i].value;
    }
  }

  return "";
}"""
