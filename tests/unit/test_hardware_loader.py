import pytest

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RegisteredDevice, RuntimeTransportConfig
from gerbera_sdk.server.hardware_loader import HardwareConfigurationResolver


@pytest.fixture
def controller():
    return Microcontroller(name="board", port="/dev/board-1", fqbn="arduino:avr:uno")


@pytest.fixture
def registered_device():
    return RegisteredDevice(
        id="board-1", address="/dev/board-1", fqbn="arduino:avr:uno", protocol="serial",
        runtime_transport=RuntimeTransportConfig.bluetooth_classic("/dev/bluetooth", "Gerbera"),
    )


def test_loader_resolves_identity_and_transport_before_runtime(controller, registered_device) -> None:
    hardware = HardwareSystem(name="robot", microcontrollers=[controller])

    HardwareConfigurationResolver({"board": registered_device}).resolve(hardware)

    assert (controller.id, controller.active_runtime_transport) == (
        "board-1", registered_device.runtime_transport,
    )


def test_loader_rejects_unregistered_controller(controller, registered_device) -> None:
    controller.port = "/dev/missing"

    with pytest.raises(ValueError, match="No configured device matched"):
        HardwareConfigurationResolver({"board": registered_device}).resolve_controller(controller)


@pytest.mark.parametrize("field, value", [("port", "/dev/other"), ("fqbn", "esp32:esp32:esp32")])
def test_loader_rejects_declaration_that_conflicts_with_registered_identity(
    controller, registered_device, field, value,
) -> None:
    controller.device_id = registered_device.id
    setattr(controller, field, value)

    with pytest.raises(ValueError, match="does not match registered device"):
        HardwareConfigurationResolver({"board": registered_device}).resolve_controller(controller)


def test_loader_preserves_explicit_runtime_transport(controller, registered_device) -> None:
    explicit = RuntimeTransportConfig.usb_serial("/dev/explicit")
    controller.runtime_transport = explicit

    HardwareConfigurationResolver({"board": registered_device}).resolve_controller(controller)

    assert controller.active_runtime_transport is explicit


def test_loader_accepts_complete_declaration_without_registry(controller) -> None:
    controller.device_id = "standalone-board"

    HardwareConfigurationResolver({}).resolve_controller(controller)

    assert controller.id == "standalone-board"


def test_loader_rejects_unresolved_identity_without_registry(controller) -> None:
    with pytest.raises(ValueError, match="No configured device matched"):
        HardwareConfigurationResolver({}).resolve_controller(controller)
