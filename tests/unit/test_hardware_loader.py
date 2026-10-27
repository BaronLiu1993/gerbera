import pytest

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RegisteredDevice, RuntimeTransportConfig
from gerbera_sdk.server.hardware_loader import HardwareConfigurationResolver


@pytest.fixture
def controller():
    return Microcontroller(
        name="board", device_id="board-1", upload_port="/dev/board-1", fqbn="arduino:avr:uno",
        runtime_transport=RuntimeTransportConfig.bluetooth_classic("/dev/bluetooth", "Gerbera"),
    )


@pytest.fixture
def registered_device():
    return RegisteredDevice(
        id="board-1", address="/dev/board-1", fqbn="arduino:avr:uno", protocol="serial",
    )


def test_loader_validates_identity_without_replacing_declared_transport(controller, registered_device) -> None:
    hardware = HardwareSystem(name="robot", microcontrollers=[controller])
    transport = controller.runtime_transport

    HardwareConfigurationResolver({"board": registered_device}).resolve(hardware)

    assert controller.id == "board-1"
    assert controller.runtime_transport is transport


def test_loader_rejects_unregistered_controller(controller, registered_device) -> None:
    controller.device_id = "unregistered"

    with pytest.raises(ValueError, match="No configured device matched"):
        HardwareConfigurationResolver({"board": registered_device}).resolve_controller(controller)


@pytest.mark.parametrize("field, value", [("upload_port", "/dev/other"), ("fqbn", "esp32:esp32:esp32")])
def test_loader_rejects_declaration_that_conflicts_with_registered_identity(
    controller, registered_device, field, value,
) -> None:
    setattr(controller, field, value)

    with pytest.raises(ValueError, match="does not match registered device"):
        HardwareConfigurationResolver({"board": registered_device}).resolve_controller(controller)


def test_loader_accepts_complete_declaration_without_registry(controller) -> None:
    controller.device_id = "standalone-board"

    HardwareConfigurationResolver({}).resolve_controller(controller)

    assert controller.id == "standalone-board"
