from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.devices.config_schema import DeviceConfig
from gerbera_sdk.firmware.devices.library import (
    ConfigFirmwareBuilder,
    load_device_config,
)


@dataclass(frozen=True)
class DeviceDefinition:
    component_type: str
    config: DeviceConfig


@dataclass(frozen=True)
class DeviceRegistry:
    definitions: tuple[DeviceDefinition, ...]
    definitions_by_type: Mapping[str, DeviceDefinition] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definitions_by_type",
            MappingProxyType(
                {
                    definition.component_type: definition
                    for definition in self.definitions
                }
            ),
        )

    def get_builder(
        self,
        component_type: str,
    ) -> BaseFirmwareBuilder:
        return ConfigFirmwareBuilder(self.get_definition(component_type).config)

    def get_definition(self, component_type: str) -> DeviceDefinition:
        try:
            return self.definitions_by_type[component_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported component type: {component_type}"
            ) from exc


def _load_device_definition(component_type: str) -> DeviceDefinition:
    return DeviceDefinition(
        component_type=component_type,
        config=load_device_config(component_type),
    )


DEVICE_DEFINITIONS = (
    _load_device_definition("dcmotor"),
    _load_device_definition("hcsr04"),
    _load_device_definition("hw201"),
    _load_device_definition("ky033"),
    _load_device_definition("led"),
    _load_device_definition("mg996r"),
    _load_device_definition("sg90"),
)

DEVICE_REGISTRY = DeviceRegistry(DEVICE_DEFINITIONS)


def get_device_builder(component_type: str):
    return DEVICE_REGISTRY.get_builder(component_type)
