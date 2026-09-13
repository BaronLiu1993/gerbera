from dataclasses import dataclass

from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.devices.library import (
    ConfigFirmwareBuilder,
    load_device_config,
)


# Mapping of the Device Name and the Builder
@dataclass(frozen=True)
class DeviceDefinition:
    component_type: str


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

        return ConfigFirmwareBuilder(load_device_config(definition.component_type))


DEVICE_DEFINITIONS = (
    DeviceDefinition("dcmotor"),
    DeviceDefinition("hcsr04"),
    DeviceDefinition("hw201"),
    DeviceDefinition("ky033"),
    DeviceDefinition("led"),
    DeviceDefinition("mg996r"),
    DeviceDefinition("sg90"),
)

DEVICE_REGISTRY = DeviceRegistry(DEVICE_DEFINITIONS)


def get_device_builder(component_type: str):
    return DEVICE_REGISTRY.get_builder(component_type)


MICROCONTROLLER_MAPPING = {
    "arduino:avr:mega": {"includes": ["Arduino.h"], "libraries": ["arduino:avr"]},
    "arduino:avr:uno": {"includes": ["Arduino.h"], "libraries": ["arduino:avr"]},
}
