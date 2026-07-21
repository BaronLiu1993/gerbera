import pytest

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def _board(port: str = "/dev/board-1") -> Microcontroller:
    return Microcontroller(port=port, fqbn="arduino:avr:uno")


def test_connection_rejects_an_unregistered_action() -> None:
    connection = Connection("led", "led", {"out": "13"})

    with pytest.raises(RuntimeError, match="not registered"):
        connection.perform_action("WRITE")


def test_connection_normalizes_registered_actions() -> None:
    connection = Connection("led", "led", {"out": "13"})
    connection.register_action(" write ", lambda params: params or {})

    assert connection.perform_action("WRITE", {"state": "on"}) == {"state": "on"}


def test_hardware_system_rejects_duplicate_board_ids(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    system = HardwareSystem()

    with pytest.raises(ValueError, match="Duplicate microcontroller in input"):
        system.add_microcontrollers([_board(), _board()])


@pytest.mark.parametrize(
    ("connections", "message"),
    [
        (
            [
                Connection("sensor", "hw201", {"out": "7"}),
                Connection("sensor", "hw201", {"out": "8"}),
            ],
            "Connection name already exists",
        ),
        (
            [
                Connection("sensor-a", "hw201", {"out": "7"}),
                Connection("sensor-b", "hw201", {"out": "7"}),
            ],
            "Pin already in use",
        ),
    ],
)
def test_microcontroller_rejects_connection_conflicts(
    device_registry,
    connections: list[Connection],
    message: str,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    board = _board()
    board.add_connections([connections[0]])

    with pytest.raises(ValueError, match=message):
        board.add_connections([connections[1]])
