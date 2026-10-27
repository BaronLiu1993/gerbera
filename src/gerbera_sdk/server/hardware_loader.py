from collections.abc import Mapping
from dataclasses import dataclass, field

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RegisteredDevice
from gerbera_sdk.server.hardware_registry import index_devices


@dataclass(frozen=True)
class HardwareConfigurationResolver:
    devices: dict[str, RegisteredDevice]
    devices_by_id: Mapping[str, RegisteredDevice] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "devices_by_id", index_devices(self.devices.values()))

    def resolve(self, hardware: HardwareSystem) -> HardwareSystem:
        for controller in hardware.microcontrollers:
            self.resolve_controller(controller)
        return hardware

    def resolve_controller(self, controller: Microcontroller) -> None:
        if not self.devices:
            return
        registered = self.find_device(controller)
        if registered is None:
            raise ValueError(f"No configured device matched controller: {controller.name}")
        if (controller.upload_port != registered.address
                or controller.fqbn != registered.fqbn):
            raise ValueError(f"Controller declaration does not match registered device: {registered.id}")

    def find_device(self, controller: Microcontroller) -> RegisteredDevice | None:
        return self.devices_by_id.get(controller.device_id)
