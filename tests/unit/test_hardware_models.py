import pytest

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
)


def make_connection(*, stream: bool = False) -> Connection:
    return Connection(
        name="status_led",
        component_type="led",
        pins={"out": "13"},
        description="Status LED",
        microcontroller_id="board-1",
        stream=stream,
    )


def test_hardware_declaration_has_no_executable_action_storage() -> None:
    assert not hasattr(make_connection(), "actions")


@pytest.mark.parametrize(
    ("stream", "expected"),
    [(False, False), (True, True)],
)
def test_connection_streaming_is_explicit(
    stream: bool,
    expected: bool,
) -> None:
    assert make_connection(stream=stream).stream_enabled is expected


def test_connection_event_name_requires_microcontroller_binding() -> None:
    connection = make_connection()
    connection.microcontroller_id = None

    with pytest.raises(RuntimeError, match="not bound"):
        _ = connection.event_name


def test_connection_event_name_is_stable_for_bound_hardware() -> None:
    connection = make_connection()

    assert connection.event_name == connection.event_name
    assert connection.event_name.startswith("status_led_")


def test_microcontroller_requires_resolved_identity_without_reading_files(monkeypatch) -> None:
    board = Microcontroller(name="board", port="/dev/board", fqbn="arduino:avr:uno")
    monkeypatch.setattr("pathlib.Path.read_text", lambda *args: pytest.fail("Unexpected filesystem read"))

    with pytest.raises(ValueError, match="device_id must be resolved"):
        _ = board.id


def test_resolved_microcontroller_identity_does_not_read_files(monkeypatch) -> None:
    board = Microcontroller(name="board", port="/dev/board", fqbn="arduino:avr:uno", device_id="board-1")
    monkeypatch.setattr("pathlib.Path.read_text", lambda *args: pytest.fail("Unexpected filesystem read"))

    assert board.id == "board-1"
