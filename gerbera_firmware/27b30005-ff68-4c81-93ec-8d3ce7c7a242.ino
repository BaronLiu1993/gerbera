#include <Arduino.h>

const int BAUD_RATE = 115200;

String readLine() {
  if (!Serial.available()) {
    return "";
  }

  return Serial.readStringUntil('\n');
}

String firstToken(String input) {
  int firstComma = input.indexOf(',');
  if (firstComma == -1) {
    return input;
  }

  return input.substring(0, firstComma);
}

String parameterValue(String input, String parameterName) {
  int start = 0;

  while (start < input.length()) {
    int commaIndex = input.indexOf(',', start);
    String token;

    if (commaIndex == -1) {
      token = input.substring(start);
      start = input.length();
    } else {
      token = input.substring(start, commaIndex);
      start = commaIndex + 1;
    }

    int firstColon = token.indexOf(':');
    int secondColon = token.indexOf(':', firstColon + 1);

    if (firstColon == -1 || secondColon == -1) {
      continue;
    }

    String tokenName = token.substring(0, firstColon);
    if (tokenName != parameterName) {
      continue;
    }

    return token.substring(secondColon + 1);
  }

  return "";
}

void setup() {
  Serial.begin(BAUD_RATE);
}

void loop() {
  String line = readLine();
  if (line.length() == 0) {
    return;
  }

  line.trim();
  String commandName = firstToken(line);
  if (commandName == "room_temperature") {
    handle_room_temperature();
    return;
  }
  Serial.println("error:unknown_command");
}

void handle_room_temperature() {
  int raw = analogRead(A0);
  float voltage = raw * (5.0 / 1023.0);
  float celsius = (voltage - 0.5) * 100.0;

  Serial.print("value:");
  Serial.print(celsius);
  Serial.println(",unit:celsius");
}
