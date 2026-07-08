from gerbera_sdk.firmware.function.devices.hw201 import HW201FirmwareBuilder


BUILDER_MAPPING = {
    "hw-201": HW201FirmwareBuilder,
    "hw201": None
}

MICROCONTROLLER_MAPPING = {
    "arduino:avr:mega": {
        "includes": ["Arduino.h"],
    },
}
