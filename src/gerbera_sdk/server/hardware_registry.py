from collections.abc import Iterable, Mapping
from functools import cached_property
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from gerbera_sdk.utils import StrictSchema
from types import MappingProxyType

from gerbera_sdk.models.hardware.microcontroller import RegisteredDevice


def index_devices(devices: Iterable[RegisteredDevice]) -> Mapping[str, RegisteredDevice]:
    indexed = {}
    addresses = set()
    for device in devices:
        if device.id in indexed:
            raise ValueError(f'Duplicate registered device ID: {device.id}')
        if device.address in addresses:
            raise ValueError(f'Duplicate registered upload address: {device.address}')
        indexed[device.id] = device
        addresses.add(device.address)
    return MappingProxyType(indexed)


class RegisteredHardwareRegistry(StrictSchema):
    model_config = ConfigDict(frozen=True)

    mode: Literal['registered'] = 'registered'
    devices: tuple[RegisteredDevice, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_devices(self):
        self.devices_by_id
        return self

    @cached_property
    def devices_by_id(self) -> Mapping[str, RegisteredDevice]:
        return index_devices(self.devices)


class StandaloneHardwareRegistry(StrictSchema):
    model_config = ConfigDict(frozen=True)

    mode: Literal['standalone'] = 'standalone'


HardwareRegistry = Annotated[
    RegisteredHardwareRegistry | StandaloneHardwareRegistry, Field(discriminator='mode'),
]
