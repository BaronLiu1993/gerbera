import pytest

from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry,
)


def test_registry_resolves_commands_out_of_order() -> None:
    registry = CommandResponseRegistry()
    first = registry.register("board-1")
    second = registry.register("board-1")

    registry.resolve(second.command_id, {})
    registry.resolve(first.command_id, {"value": "first"})

    assert (
        registry.wait(first, 0),
        registry.wait(second, 0),
    ) == (
        {"value": "first"},
        {},
    )


def test_registry_propagates_board_errors() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register("board-1")
    registry.fail(pending.command_id, "invalid_state")

    with pytest.raises(RuntimeError, match="invalid_state"):
        registry.wait(pending, 0)


def test_registry_fails_only_disconnected_board_commands() -> None:
    registry = CommandResponseRegistry()
    disconnected = registry.register("board-1")
    connected = registry.register("board-2")

    registry.fail_board("board-1", "disconnected")

    assert (
        disconnected.error,
        connected.error,
        connected.command_id in registry.pending_commands,
    ) == ("disconnected", None, True)


def test_registry_times_out_unacknowledged_command() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register("board-1")

    with pytest.raises(TimeoutError, match="command response timed out"):
        registry.wait(pending, 0)

    assert registry.pending_commands == {}


def test_registry_rejects_completion_without_response_payload() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register("board-1")
    pending.completion.set()

    with pytest.raises(RuntimeError, match="without a response"):
        registry.wait(pending, 0)
