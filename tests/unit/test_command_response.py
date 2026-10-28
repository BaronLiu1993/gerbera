import pytest

from gerbera_sdk.models.runtime.commands.payload_contract import PayloadContract
from gerbera_sdk.firmware.devices.config_schema import StateFieldConfig
from gerbera_sdk.firmware.parameter_schema import NumericRange
from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry, CommandRoute, CommandReply,
)


def test_registry_resolves_commands_out_of_order() -> None:
    registry = CommandResponseRegistry()
    first = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({"value": StateFieldConfig(None, NumericRange(kind="range", minimum=None, maximum=None))}))
    second = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))

    registry.resolve(CommandReply(second.command_id, second.route, {}))
    registry.resolve(CommandReply(first.command_id, first.route, {"value": "1"}))

    assert (
        registry.wait(first, 0),
        registry.wait(second, 0),
    ) == (
        {"value": "1"},
        {},
    )


def test_registry_propagates_board_errors() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))
    registry.resolve(CommandReply(pending.command_id, pending.route, {"error": "invalid_state"}))

    with pytest.raises(RuntimeError, match="invalid_state"):
        registry.wait(pending, 0)


def test_registry_fails_only_disconnected_board_commands() -> None:
    registry = CommandResponseRegistry()
    disconnected = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))
    connected = registry.register(CommandRoute("board-2", "sensor_event"), PayloadContract({}))

    registry.fail_board("board-1", "disconnected")

    assert (
        disconnected.error,
        connected.error,
        connected.command_id in registry.pending_commands,
    ) == ("disconnected", None, True)


def test_registry_times_out_unacknowledged_command() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))

    with pytest.raises(TimeoutError, match="command response timed out"):
        registry.wait(pending, 0)

    assert registry.pending_commands == {}


def test_registry_rejects_completion_without_response_payload() -> None:
    registry = CommandResponseRegistry()
    pending = registry.register(CommandRoute("board-1", "sensor_event"), PayloadContract({}))
    pending.completion.set()

    with pytest.raises(RuntimeError, match="without a response"):
        registry.wait(pending, 0)


@pytest.mark.parametrize("payload", [
    {"unknown": "1"}, {"led_state": "0.5"}, {"led_state": "nan"},
    {"error": "invalid_state", "led_state": "1"},
])
def test_registry_validates_payload_before_completion(payload):
    registry = CommandResponseRegistry()
    field = get_device_builder("led").config.state.fields["led_state"]
    pending = registry.register(CommandRoute("board-1", "led_event"), PayloadContract({"led_state": field}))

    with pytest.raises(ValueError):
        registry.resolve(CommandReply(pending.command_id, pending.route, payload))

    assert not pending.completion.is_set()
    assert pending.command_id in registry.pending_commands
