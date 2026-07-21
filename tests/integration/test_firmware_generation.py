from gerbera_sdk.firmware.generator import Generator
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def test_models_generate_routed_firmware_for_read_and_write_components(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    board = Microcontroller(port="/dev/board-1", fqbn="arduino:avr:uno")
    board.add_connections(
        [
            Connection("sensor", "hw201", {"out": "7"}),
            Connection("status_led", "led", {"out": "13"}),
        ]
    )

    firmware = Generator.build_firmware(board)

    assert "#include <Arduino.h>" in firmware
    assert "void handle_sensor" in firmware
    assert "void handle_status_led" in firmware
    assert 'action == "READ" && commandName == "sensor"' in firmware
    assert 'action == "WRITE" && commandName == "status_led"' in firmware
