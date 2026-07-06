from gerbera_sdk import Connection, GerberaMCPServer, HardwareSystem, Microcontroller
from gerbera_sdk.mcp.transport_pool import SerialTransportPool


def test_serial_transport_pool_reuses_persistent_connections(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    created_connections: list[object] = []

    class FakeSerialConnection:
        def __init__(self) -> None:
            self.connect_calls: list[tuple[str, int]] = []
            self.send_calls: list[str] = []
            self.destroy_called = False
            created_connections.append(self)

        def connect(self, port: str, baud: int = 115200) -> None:
            self.connect_calls.append((port, baud))

        def send(self, command: str) -> str:
            self.send_calls.append(command)
            return "value:23.5,unit:celsius"

        def destroy(self) -> None:
            self.destroy_called = True

    monkeypatch.setattr(
        "gerbera_sdk.mcp.transport_pool.SerialConnection",
        FakeSerialConnection,
    )

    hardware_system = HardwareSystem(
        microcontrollers=[
            Microcontroller(
                id="board-1",
                baud_rate=115200,
                connections=[
                    Connection(
                        microcontroller_id="board-1",
                        name="room_temperature",
                        description="Temperature sensor.",
                        pins={"signal": "A0"},
                        component_type="hw-201",
                    )
                ],
            )
        ]
    )
    transport_pool = SerialTransportPool(hardware_system)

    first_response = transport_pool.execute("board-1", "room_temperature")
    second_response = transport_pool.execute("board-1", "room_temperature")
    transport_pool.close_all()

    assert first_response == {"value": 23.5, "unit": "celsius"}
    assert second_response == {"value": 23.5, "unit": "celsius"}
    assert len(created_connections) == 1
    assert created_connections[0].connect_calls == [("/dev/cu.usbserial-1140", 115200)]
    assert created_connections[0].send_calls == [
        "room_temperature",
        "room_temperature",
    ]
    assert created_connections[0].destroy_called is True


def test_create_server_raises_without_fastmcp_dependency(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)
    monkeypatch.setattr("gerbera_sdk.mcp.server.FastMCP", None)

    hardware_system = HardwareSystem(
        microcontrollers=[Microcontroller(id="board-1")]
    )

    try:
        GerberaMCPServer(hardware_system).create_server()
    except ImportError as exc:
        assert "fastmcp is not installed" in str(exc)
    else:
        raise AssertionError("Expected missing fastmcp dependency error")


def test_create_server_builds_overview_and_connection_tools(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    class FakeFastMCP:
        def __init__(self, name, instructions=None, tools=None):
            self.name = name
            self.instructions = instructions
            self.tools = tools or []

        def run(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr("gerbera_sdk.mcp.server.FastMCP", FakeFastMCP)

    hardware_system = HardwareSystem(
        description="Kitchen system",
        microcontrollers=[
            Microcontroller(
                id="board-1",
                baud_rate=115200,
                connections=[
                    Connection(
                        microcontroller_id="board-1",
                        name="room_temperature",
                        description="Temperature sensor.",
                        pins={"signal": "A0"},
                        component_type="hw-201",
                    )
                ],
            )
        ],
    )
    server = GerberaMCPServer(hardware_system)

    def fake_execute(microcontroller_id: str, connection_name: str) -> dict[str, object]:
        assert microcontroller_id == "board-1"
        assert connection_name == "room_temperature"
        return {"value": 22.5, "unit": "celsius"}

    monkeypatch.setattr(server.transport_pool, "execute", fake_execute)

    fastmcp_server = server.create_server()
    tools_by_name = {tool.__name__: tool for tool in fastmcp_server.tools}

    assert fastmcp_server.name == "Gerbera MCP Server"
    assert "overview tool first" in fastmcp_server.instructions
    assert set(tools_by_name.keys()) == {
        "gerbera_hardware_overview",
        "room_temperature",
    }
    assert tools_by_name["gerbera_hardware_overview"]()["description"] == "Kitchen system"
    assert tools_by_name["room_temperature"]() == {
        "value": 22.5,
        "unit": "celsius",
    }
