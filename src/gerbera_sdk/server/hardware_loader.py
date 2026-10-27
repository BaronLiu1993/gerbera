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
        registered = self.find_device(controller)
        if registered is None:
            if controller.device_id is None or self.devices:
                raise ValueError(f"No configured device matched controller: {controller.name}")
            return
        if (controller.firmware_upload_port != registered.address
                or controller.fqbn != registered.fqbn):
            raise ValueError(f"Controller declaration does not match registered device: {registered.id}")
        controller.device_id = registered.id
        if controller.runtime_transport is None:
            controller.runtime_transport = registered.runtime_transport

    def find_device(self, controller: Microcontroller) -> RegisteredDevice | None:
        for device in self.devices.values():
            if controller.device_id is not None:
                if device.id == controller.device_id:
                    return device
            elif device.address == controller.firmware_upload_port:
                return device
        return None
