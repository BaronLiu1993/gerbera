from gerbera_sdk.firmware.devices.dcmotor import DCMotorFirmwareBuilder
from gerbera_sdk.firmware.devices.hw201 import HW201FirmwareBuilder
from gerbera_sdk.firmware.devices.hcsr04 import HCSR04FirmwareBuilder
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder
from gerbera_sdk.firmware.devices.mg996r import MG996RFirmwareBuilder
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


DEVICES_MAPPING = {
    "dcmotor": DCMotorFirmwareBuilder,
    "hw201": HW201FirmwareBuilder,
    "hcsr04": HCSR04FirmwareBuilder,
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
