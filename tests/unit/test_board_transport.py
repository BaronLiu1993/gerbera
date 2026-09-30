from dataclasses import replace

from gerbera_sdk.firmware.board_definitions import ESP32_DEV_MODULE
from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard
from gerbera_sdk.models.hardware.microcontroller import (
    RuntimeTransportConfig,
    RuntimeWatchdogConfig,
)
from gerbera_sdk.models.runtime.board_transport import (
    BoardTransportFactory,
    SerialBoardTransport,
)


def make_board(transport: RuntimeTransportConfig) -> ResolvedBoard:
    return ResolvedBoard(
        microcontroller_id="esp32-1",
        name="esp32",
        port=transport.port,
        baud_rate=115200,
        definition=ESP32_DEV_MODULE,
        connections=(),
        watchdog=RuntimeWatchdogConfig(500, 2500),
        contract_digest="digest",
        upload_port="/dev/usb-esp32",
        runtime_transport=transport,
    )


def test_bluetooth_transport_does_not_wait_for_usb_boot() -> None:
    board = make_board(
        RuntimeTransportConfig.bluetooth_classic(
            "/dev/bluetooth-esp32",
            "Gerbera-ESP32",
        )
    )

    transport = BoardTransportFactory.create(board)

    assert isinstance(transport, SerialBoardTransport)
    assert transport.boot_wait_seconds == 0


def test_usb_transport_keeps_board_boot_wait() -> None:
    bluetooth_board = make_board(
        RuntimeTransportConfig.bluetooth_classic(
            "/dev/bluetooth-esp32",
            "Gerbera-ESP32",
        )
    )
    usb_board = replace(
        bluetooth_board,
        runtime_transport=RuntimeTransportConfig.usb_serial("/dev/usb-esp32"),
    )

    transport = BoardTransportFactory.create(usb_board)

    assert isinstance(transport, SerialBoardTransport)
    assert transport.boot_wait_seconds > 0
