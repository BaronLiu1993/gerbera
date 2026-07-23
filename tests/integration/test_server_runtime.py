import asyncio
from types import SimpleNamespace

from fastmcp import FastMCP
import pytest

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


class FakeApp:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str, description: str):
        def register(function):
            self.tools[name] = function
            return function

        return register


class FakeSerialConnection:
    def __init__(self) -> None:
        self.commands = []

    def send(self, command: str) -> str:
        self.commands.append(command)
        return "state:on"


def test_server_registers_tools_that_execute_through_the_board_runtime(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    board = Microcontroller(port="/dev/board-1", fqbn="arduino:avr:uno")
    board.add_connections([Connection("status_led", "led", {"out": "13"})])
    hardware_system = HardwareSystem(microcontrollers=[board])
    serial_connection = FakeSerialConnection()
    board_runtime = SimpleNamespace(
        serial_pool={"board-1": serial_connection},
        get_serial_connection=lambda microcontroller: serial_connection,
    )
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=hardware_system,
        board_runtime=board_runtime,
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
    )

    runtime._register_events()
    GerberaRuntime._register_server_runtime_tools(runtime)
    response = app.tools["turn_on_status_led"]()

    assert response == {"state": "on"}
    assert serial_connection.commands == ["WRITE,status_led,state:on"]
    assert set(app.tools) == {
        "write_status_led",
        "turn_on_status_led",
        "turn_off_status_led",
    }


def test_server_registers_command_spec_as_mcp_tool_schema() -> None:
    connection = Connection("motor", "sg90", {"signal": "7"})
    command = CommandCompiler.command_specs(connection)[0]
    captured_params = []
    connection.register_action(
        "WRITE",
        lambda params: captured_params.append(params) or params,
    )

    event_bus = EventBus()
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=object(),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
    )
    runtime._register_connection_tool(connection, command)

    tool = asyncio.run(app.get_tool("write_motor"))
    params_schema = tool.parameters["$defs"]["MotorWriteParams"]
    assert tool.description == "Set servo angle."
    assert params_schema == {
        "additionalProperties": False,
        "properties": {
            "angle": {
                "description": "Servo angle in degrees.",
                "maximum": 180,
                "minimum": 0,
                "type": "integer",
            }
        },
        "required": ["angle"],
        "type": "object",
    }

    asyncio.run(tool.run({"params": {"angle": 90}}))
    assert captured_params == [{"angle": "90"}]

    with pytest.raises(ValueError, match="less than or equal to 180"):
        asyncio.run(tool.run({"params": {"angle": 181}}))
