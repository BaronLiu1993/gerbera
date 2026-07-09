# Generate Parsed Script
class Parser:
    @staticmethod
    def parse_command_code() -> str:
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
