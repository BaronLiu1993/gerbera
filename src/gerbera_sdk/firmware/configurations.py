from dataclasses import dataclass

from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.devices.dcmotor import DCMotorFirmwareBuilder
from gerbera_sdk.firmware.devices.hw201 import HW201FirmwareBuilder
from gerbera_sdk.firmware.devices.hcsr04 import HCSR04FirmwareBuilder
from gerbera_sdk.firmware.devices.ky033 import KY033FirmwareBuilder
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder
from gerbera_sdk.firmware.devices.mg996r import MG996RFirmwareBuilder
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


# Mapping of the Device Name and the Builder
@dataclass(frozen=True)
class DeviceDefinition:
    component_type: str
    builder_type: type[BaseFirmwareBuilder]


@dataclass(frozen=True)
class DeviceRegistry:
    definitions: tuple[DeviceDefinition, ...]

    @property
    def definitions_by_type(self) -> dict[str, DeviceDefinition]:
        return {
            definition.component_type: definition for definition in self.definitions
        }

    def get_builder(
        self,
        component_type: str,
    ) -> BaseFirmwareBuilder:
        definition = self.definitions_by_type.get(component_type)
        if definition is None:
            raise ValueError(f"Unsupported component type: {component_type}")

        return definition.builder_type()


DEVICE_DEFINITIONS = (
    DeviceDefinition("dcmotor", DCMotorFirmwareBuilder),
    DeviceDefinition("hcsr04", HCSR04FirmwareBuilder),
    DeviceDefinition("hw201", HW201FirmwareBuilder),
    DeviceDefinition("ky033", KY033FirmwareBuilder),
    DeviceDefinition("led", LEDFirmwareBuilder),
    DeviceDefinition("mg996r", MG996RFirmwareBuilder),
    DeviceDefinition("sg90", SG90FirmwareBuilder),
)

DEVICE_REGISTRY = DeviceRegistry(DEVICE_DEFINITIONS)


def get_device_builder(component_type: str):
    return DEVICE_REGISTRY.get_builder(component_type)


MICROCONTROLLER_MAPPING = {
    "arduino:avr:mega": {"includes": ["Arduino.h"], "libraries": ["arduino:avr"]},
    "arduino:avr:uno": {"includes": ["Arduino.h"], "libraries": ["arduino:avr"]},
}
