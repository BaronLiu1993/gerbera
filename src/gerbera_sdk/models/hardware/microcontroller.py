from dataclasses import dataclass, field
import json

from gerbera_sdk.models.hardware.connection import Connection

CONFIG = json.loads("config.json")


@dataclass
class Microcontroller:
    microcontroller_id: str
    connections: list[Connection] = field(default_factory=list)

    @property
    def upload_port(self):
        return CONFIG[self.microcontroller_id]["upload_port"]

    @property
    def fqbn(self):
        return CONFIG[self.microcontroller_id]["fqbn"]

    @property
    def baud_rate(self):
        return CONFIG[self.microcontroller_id]['baud_rate']


class ArduinoUno(Microcontroller):
    includes = "Arduino.h"
    library = "Arduino"
    pins = frozenset(
        {
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "10", "11", "12", "13", "A0", "A1", "A2", "A3", "A4", "A5",
        }
    )


class ESP32(Microcontroller):
    includes = "Arduino.h"
    library = "ESP32"
    pins = frozenset(
        {
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
            "12", "13", "14", "15", "16", "17", "18", "19", "21", "22",
            "23", "25", "26", "27", "32", "33", "34", "35", "36", "39",
        }
    )
