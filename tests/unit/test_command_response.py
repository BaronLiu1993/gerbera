import pytest

from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry, CommandRoute, CommandReply,
)


def test_registry_resolves_commands_out_of_order() -> None:
    registry = CommandResponseRegistry()
    first = registry.register(CommandRoute("board-1", "sensor_event"))
    second = registry.register(CommandRoute("board-1", "sensor_event"))

    registry.resolve(CommandReply(second.command_id, second.route, {}))
    registry.resolve(CommandReply(first.command_id, first.route, {"value": "first"}))

    assert (
        registry.wait(first, 0),
        registry.wait(second, 0),
    ) == (
        {"value": "first"},
        {},
    )


def test_registry_propagates_board_errors() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"))
    registry.resolve(CommandReply(pending.command_id, pending.route, {"error": "invalid_state"}))

    with pytest.raises(RuntimeError, match="invalid_state"):
        registry.wait(pending, 0)


def test_registry_fails_only_disconnected_board_commands() -> None:
    registry = CommandResponseRegistry()
    disconnected = registry.register(CommandRoute("board-1", "sensor_event"))
    connected = registry.register(CommandRoute("board-2", "sensor_event"))

    registry.fail_board("board-1", "disconnected")

    assert (
        disconnected.error,
        connected.error,
        connected.command_id in registry.pending_commands,
    ) == ("disconnected", None, True)


def test_registry_times_out_unacknowledged_command() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"))

    with pytest.raises(TimeoutError, match="command response timed out"):
        registry.wait(pending, 0)

    assert registry.pending_commands == {}


def test_registry_rejects_completion_without_response_payload() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"))
    pending.completion.set()

    with pytest.raises(RuntimeError, match="without a response"):
        registry.wait(pending, 0)
