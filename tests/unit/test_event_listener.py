from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry,
)


def make_listener(reconnect_board) -> EventListener:
    dependency = SimpleNamespace()
    return EventListener(
        hardware_plan=dependency,
        transport_pool={},
        event_bus=dependency,
        reaction_bus=dependency,
        hardware_runtime=dependency,
        command_responses=CommandResponseRegistry(),
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


def test_malformed_message_does_not_stop_later_events() -> None:
    received_payloads = []
    updated_states = []
    listener = None

    class Transport:
        lines = iter(
            (
                b"malformed\n",
                b"MCP,status_event,led_state:1\n",
                b"",
            )
        )

        def readline(self):
            line = next(self.lines)
            if not line:
                listener.stop_event.set()
            return line

    class ReactionBus:
        async def update_reaction_value(self, *args):
            return None

    connection = Connection(
        name="status",
        component_type="led",
        pins={"out": "13"},
        description="Status LED",
        microcontroller_id="board-1",
    )
    event = SimpleNamespace(
        component_type="led",
        perform_work=received_payloads.append,
    )
    listener = EventListener(
        hardware_plan=SimpleNamespace(
            connections_by_event_route={
                ("board-1", "status_event"): connection,
            }
        ),
        transport_pool={"board-1": Transport()},
        event_bus=SimpleNamespace(get_event=lambda *args: event),
        reaction_bus=ReactionBus(),
        hardware_runtime=SimpleNamespace(
            update_state=lambda key, state: updated_states.append((key, state))
        ),
        command_responses=CommandResponseRegistry(),
    )

    listener.listen_loop("board-1")
    listener.reaction_executor.shutdown(wait=True)

    assert received_payloads == [{"led_state": "1"}]
    assert updated_states[0][0] == ("board-1", "status", "led_state")
    health = listener.get_health()["board-1"]
    assert health["malformed_message_count"] == 1
    assert health["last_successful_message_at"] is not None
