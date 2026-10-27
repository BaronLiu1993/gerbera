from dataclasses import dataclass

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RegisteredDevice
from gerbera_sdk.server.hardware_registry import HardwareRegistry, RegisteredHardwareRegistry, StandaloneHardwareRegistry


@dataclass(frozen=True)
class HardwareConfigurationResolver:
    registry: HardwareRegistry

    def __post_init__(self):
        if not isinstance(self.registry, (RegisteredHardwareRegistry, StandaloneHardwareRegistry)):
            raise TypeError("An explicit hardware registry mode is required")

    def resolve(self, hardware: HardwareSystem) -> HardwareSystem:
        for controller in hardware.microcontrollers:
            self.resolve_controller(controller)
        return hardware

    def resolve_controller(self, controller: Microcontroller) -> None:
        if isinstance(self.registry, StandaloneHardwareRegistry):
            return
        registered = self.find_device(controller)
        if registered is None:
            raise ValueError(f"No configured device matched controller: {controller.name}")
        if (controller.upload_port != registered.address
                or controller.fqbn != registered.fqbn):
            raise ValueError(f"Controller declaration does not match registered device: {registered.id}")

    def find_device(self, controller: Microcontroller) -> RegisteredDevice | None:
        if isinstance(self.registry, StandaloneHardwareRegistry):
            raise ValueError("Standalone hardware does not use a device registry")
        return self.registry.devices_by_id.get(controller.device_id)
