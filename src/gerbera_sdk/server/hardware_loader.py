from dataclasses import dataclass

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RegisteredDevice


@dataclass(frozen=True)
class HardwareConfigurationResolver:
    devices: dict[str, RegisteredDevice]

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
        for device in self.devices.values():
            if device.id == controller.device_id:
                return device
        return None
