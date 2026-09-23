from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def test_models_generate_routed_firmware_for_read_and_write_components(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    board = Microcontroller(
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        connections=[
            Connection(
                "sensor",
                "hw201",
                {"out": "7"},
                "Infrared sensor",
                microcontroller_id="board-1",
                stream=True,
            ),
            Connection(
                "status_led",
                "led",
                {"out": "13"},
                "Status LED",
                microcontroller_id="board-1",
            ),
        ],
    )

    firmware = FirmwareGenerator(board).build()

    assert "#include <Arduino.h>" in firmware
    assert "void handle_sensor" in firmware
    assert "void handle_status_led" in firmware
    assert 'action == "READ" && commandName == "sensor"' in firmware
    assert 'action == "WRITE" && commandName == "status_led"' in firmware
    assert "sensor_stream_on" in firmware
    assert f"STREAM,{board.connections[0].event_name}" in firmware
