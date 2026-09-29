from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeWatchdogConfig,
)


def test_models_generate_routed_firmware_for_read_and_write_components(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    board = Microcontroller(
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
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

    firmware = FirmwareGenerator(board).generate()

    assert '#include "GerberaRuntime.h"' in firmware.sketch
    assert "void handle_sensor" in firmware.commands_source
    assert "void handle_status_led" in firmware.commands_source
    assert (
        'action == "READ" && commandName == "sensor"'
        in firmware.commands_source
    )
    assert (
        'action == "WRITE" && commandName == "status_led"'
        in firmware.commands_source
    )
    assert 'action == "HANDSHAKE"' in firmware.runtime_source
    assert "GERBERA_CONTRACT_DIGEST" in firmware.runtime_source
    assert "sensor_stream_on" in firmware.components_source
    stream_name = f"STREAM,{board.connections[0].event_name}"
    assert stream_name in firmware.commands_source
    assert "component_feedback_lost" in firmware.runtime_source
    assert "error:hardware_not_ready" in firmware.commands_source
