from gerbera_sdk import gerbera_runtime as runtime_module
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeWatchdogConfig,
)


def test_runtime_binds_connections_to_their_microcontroller() -> None:
    connection = Connection(name="sensor", component_type="hw201", pins={"out": "7"}, description="Sensor")
    board = Microcontroller(
        name="board", device_id="board-a", fqbn="arduino:avr:uno", port="/dev/test", connections=[connection],
    )
    hardware = HardwareSystem(id="system-1", name="robot", microcontrollers=[board])

    GerberaRuntime.bind_connection_microcontroller_ids(hardware)

    assert (connection.microcontroller_id, board.hardware_system_id) == ("board-a", "system-1")


def test_runtime_builds_writer_database_from_explicit_connection_details() -> None:
    database = GerberaRuntime.runtime_database(
        host="database.internal",
        port=5432,
        password="secret",
    )

    assert database == Database(
        host="database.internal",
        port=5432,
        user="gerbera_writer",
        password="secret",
        database_name="gerbera",
    )


def test_runtime_shares_acknowledgement_registry(monkeypatch) -> None:
    registries = {}

    class CapturingEventListener:
        def __init__(self, **dependencies) -> None:
            registries["listener"] = dependencies[
                "command_responses"
            ]

    class CapturingServerRuntime:
        def __init__(self, **dependencies) -> None:
            registries["server"] = dependencies[
                "command_responses"
            ]

        def register_events(self) -> None:
            return None

        def register_tools(self) -> None:
            return None

    class InactiveMcpServer:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def run(self, **kwargs) -> None:
            return None

        def custom_route(self, *args, **kwargs):
            return lambda function: function

        def resource(self, *args, **kwargs):
            return lambda function: function

    monkeypatch.setattr(
        runtime_module,
        "EventListener",
        CapturingEventListener,
    )
    monkeypatch.setattr(
        runtime_module,
        "ServerRuntime",
        CapturingServerRuntime,
    )
    monkeypatch.setattr(runtime_module, "FastMCP", InactiveMcpServer)

    GerberaRuntime.run(
        HardwareSystem(name="test"),
        transport="http",
        database_host="localhost",
        database_port=5432,
        database_password="secret",
    )

    assert registries["listener"] is registries["server"]
