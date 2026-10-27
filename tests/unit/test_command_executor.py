from types import SimpleNamespace

import pytest

from gerbera_sdk.models.runtime.commands.command_response import CommandReply, CommandRoute
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RuntimeTransportConfig
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry


@pytest.fixture
def command_setup():
    connection = Connection(name="sensor", component_type="hw201", pins={"out": "7"}, description="Sensor")
    hardware = HardwareSystem(name="robot", microcontrollers=[Microcontroller(
        runtime_transport=RuntimeTransportConfig.usb_serial("/dev/test"),
        name="board", device_id="board-1", upload_port="/dev/test", fqbn="arduino:avr:uno", connections=[connection],
    )])
    GerberaRuntime.bind_connection_microcontroller_ids(hardware)
    plan = GerberaRuntime.validate_hardware(hardware)
    responses = CommandResponseRegistry()
    return SimpleNamespace(connection=connection, plan=plan, responses=responses)


def test_bound_action_receives_correlated_board_response_without_mcp(command_setup) -> None:
    def reply(command):
        message = SerialMessageCodec.decode(command)
        command_setup.responses.resolve(CommandReply(message.fields["command_id"], CommandRoute("board-1", command_setup.connection.event_name), {"obstacle_detected": "1"}))

    boards = SimpleNamespace(get_transport=lambda board_id: SimpleNamespace(write=reply))
    executor = CommandExecutor(command_setup.plan, boards, command_setup.responses)

    assert executor.execute_declared(command_setup.connection, "READ", {}) == {
        "success": True, "value": {"obstacle_detected": "1"},
    }


def test_command_timeout_cleans_pending_response(command_setup) -> None:
    boards = SimpleNamespace(get_transport=lambda board_id: SimpleNamespace(write=lambda command: None))
    executor = CommandExecutor(command_setup.plan, boards, command_setup.responses, timeout_seconds=0)
    connection = command_setup.plan.boards[0].connections[0]

    result = executor.execute(connection, "READ", {})

    assert (result["success"], "timed out" in result["error"], command_setup.responses.pending_commands) == (False, True, {})


def test_transport_error_cleans_pending_response(command_setup) -> None:
    def unavailable(board_id):
        raise OSError("disconnected")

    executor = CommandExecutor(command_setup.plan, SimpleNamespace(get_transport=unavailable), command_setup.responses)

    result = executor.execute(command_setup.plan.boards[0].connections[0], "READ", {})

    assert (result, command_setup.responses.pending_commands) == ({"success": False, "error": "disconnected"}, {})
