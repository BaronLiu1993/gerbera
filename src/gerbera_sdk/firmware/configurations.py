from gerbera_sdk.firmware.devices.dcmotor import DCMotorFirmwareBuilder
from gerbera_sdk.firmware.devices.hw201 import HW201FirmwareBuilder
from gerbera_sdk.firmware.devices.hcsr04 import HCSR04FirmwareBuilder
from gerbera_sdk.firmware.devices.ky033 import KY033FirmwareBuilder
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder
from gerbera_sdk.firmware.devices.mg996r import MG996RFirmwareBuilder
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


DEVICES_MAPPING = {
    "dcmotor": DCMotorFirmwareBuilder,
    "hw201": HW201FirmwareBuilder,
    "hcsr04": HCSR04FirmwareBuilder,
    "ky033": KY033FirmwareBuilder,
    "led": LEDFirmwareBuilder,
    "mg996r": MG996RFirmwareBuilder,
    "sg90": SG90FirmwareBuilder,
}


def get_device_builder(component_type: str, context: str = "device"):
    if component_type not in DEVICES_MAPPING:
        raise ValueError(
            f"Unsupported component type for {context}: {component_type}"
        )

    return DEVICES_MAPPING[component_type]()

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
