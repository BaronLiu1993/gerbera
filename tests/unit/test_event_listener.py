from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gerbera_sdk.models.runtime.commands.payload_contract import PayloadContract
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry, CommandRoute,
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


@pytest.mark.parametrize("board, target", [("board-2", "sensor_event"), ("board-1", "wrong_event")])
def test_reply_cannot_complete_a_command_owned_by_another_route(board, target):
    listener = make_listener(None)
    pending = listener.command_responses.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))
    try:
        with pytest.raises(ValueError, match="route does not match"):
            listener.process_message(board, f"MCP,{target},command_id:{pending.command_id},value:1")
        assert not pending.completion.is_set()
        assert pending.command_id in listener.command_responses.pending_commands
    finally:
        listener.reaction_executor.shutdown(wait=True)


def test_invalid_wire_payload_cannot_update_event_storage_or_state():
    listener = make_listener(None)
    connection = Connection("status", "led", {"out": "13"}, "LED", microcontroller_id="board-1")
    handler = SimpleNamespace(component_type="led", perform_work=Mock())
    listener.hardware_plan.connections_by_event_route = {("board-1", "led_event"): connection}
    listener.event_bus.get_event = lambda *args: handler
    listener.hardware_runtime.update_state = Mock()
    try:
        with pytest.raises(ValueError):
            listener.process_message("board-1", "MCP,led_event,led_state:0.5")
        handler.perform_work.assert_not_called()
        listener.hardware_runtime.update_state.assert_not_called()
    finally:
        listener.reaction_executor.shutdown(wait=True)


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
