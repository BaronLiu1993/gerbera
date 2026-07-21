from types import SimpleNamespace

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


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
