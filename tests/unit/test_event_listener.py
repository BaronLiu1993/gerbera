from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event_listener import EventListener


def make_listener(reconnect_board) -> EventListener:
    dependency = SimpleNamespace()
    return EventListener(
        hardware_plan=dependency,
        transport_pool={},
        event_bus=dependency,
        reaction_bus=dependency,
        hardware_runtime=dependency,
        reconnect_board=reconnect_board,
    )


def test_listener_retries_a_disconnected_board(monkeypatch) -> None:
    attempts = 0

    def reconnect_board(microcontroller_id: str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError("still disconnected")

    monkeypatch.setattr(
        "gerbera_sdk.events.event_listener.time.sleep",
        lambda delay: None,
    )

    make_listener(reconnect_board).reconnect("board-1")

    assert attempts == 3


def test_listener_reports_exhausted_reconnect_attempts(monkeypatch) -> None:
    def reconnect_board(microcontroller_id: str) -> None:
        raise OSError("still disconnected")

    monkeypatch.setattr(
        "gerbera_sdk.events.event_listener.time.sleep",
        lambda delay: None,
    )

    with pytest.raises(RuntimeError, match="Could not reconnect board"):
        make_listener(reconnect_board).reconnect("board-1")
