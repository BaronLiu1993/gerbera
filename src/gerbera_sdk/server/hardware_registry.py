from collections.abc import Iterable, Mapping
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
