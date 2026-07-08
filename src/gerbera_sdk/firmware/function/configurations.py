from gerbera_sdk.firmware.function.devices.hw201 import HW201FirmwareBuilder


DEVICES_MAPPING = {
    "hw-201": HW201FirmwareBuilder,
    "hw201": None
}

MICROCONTROLLER_MAPPING = {
    "arduino:avr:mega": {
        "includes": ["Arduino.h"],
        "libraries": ["arduino:avr"]
    },
    "arduino:avr:uno": {
        "includes": ["Arduino.h"],
        "libraries": ["arduino:avr"]
    },
}
