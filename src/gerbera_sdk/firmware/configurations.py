from gerbera_sdk.firmware.devices.hw201 import HW201FirmwareBuilder
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder
from gerbera_sdk.firmware.devices.mg996r import MG996RFirmwareBuilder
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


DEVICES_MAPPING = {
    "hw201": HW201FirmwareBuilder,
    "led": LEDFirmwareBuilder,
    "mg996r": MG996RFirmwareBuilder,
    "sg90": SG90FirmwareBuilder,
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
