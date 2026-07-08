from gerbera_sdk.MCP.function.devices.hw201 import HW201FirmwareBuilder


BUILDER_MAPPING = {
    "hw201": HW201FirmwareBuilder,
}

MICROCONTROLLER_MAPPING = {
    "arduino:avr:mega": {
        "includes": ["Arduino.h"],
    },
}
