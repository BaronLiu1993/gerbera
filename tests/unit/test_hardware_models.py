import json

import pytest

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


def make_connection(*, stream: bool = False) -> Connection:
    return Connection(
        name="status-led",
        component_type="led",
        pins={"out": "13"},
        description="Status LED",
        microcontroller_id="board-1",
        stream=stream,
    )


def test_connection_runs_a_registered_action_with_normalized_name() -> None:
    connection = make_connection()
    connection.register_action(" write ", lambda params: params)

    result = connection.perform_action("WRITE", {"state": "on"})

    assert result == {"state": "on"}


def test_connection_rejects_an_unregistered_action() -> None:
    connection = make_connection()

    with pytest.raises(RuntimeError, match="not registered"):
        connection.perform_action("WRITE", {})


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
    assert connection.event_name.startswith("led_")


def test_microcontroller_resolves_id_from_its_configured_registry(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "devices": {
                    "board-1": {
                        "id": "board-1",
                        "address": "/dev/board-1",
                    }
                }
            }
        )
    )
    board = Microcontroller(
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        config_path=config_path,
    )

    assert board.id == "board-1"


def test_microcontroller_hard_fails_when_port_is_not_registered(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "devices": {
                    "board-1": {
                        "id": "board-1",
                        "address": "/dev/other",
                    }
                }
            }
        )
    )
    board = Microcontroller(
        name="board",
        port="/dev/missing",
        fqbn="arduino:avr:uno",
        config_path=config_path,
    )

    with pytest.raises(ValueError, match="matched port"):
        _ = board.id
