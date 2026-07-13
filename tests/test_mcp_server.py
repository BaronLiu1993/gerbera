from gerbera_sdk import Connection, GerberaServer, HardwareSystem, Microcontroller


class FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.registered_tools: dict[str, object] = {}

    def tool(self, name: str, description: str):
        def decorator(func):
            func.__doc__ = description
            self.registered_tools[name] = func
            return func

        return decorator

    def run(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeSerialConnection:
    def __init__(self) -> None:
        self.connect_calls: list[tuple[str, int]] = []
        self.send_calls: list[str] = []
        self.destroy_called = False

    def connect(self, port: str, baud: int = 115200) -> None:
        self.connect_calls.append((port, baud))

    def send(self, command: str) -> str:
        self.send_calls.append(command)
        return "value:1"

    def destroy(self) -> None:
        self.destroy_called = True


class FakeDatabase:
    def __init__(self) -> None:
        self.created_tables: list[tuple[str, object]] = []
        self.writes: list[tuple[str, list[dict[str, str]]]] = []

    def create_database_table(self, table_name: str, schema) -> None:
        self.created_tables.append((table_name, schema))

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        self.writes.append((table_name, payload))


def build_hardware_system() -> HardwareSystem:
    hardware_system = HardwareSystem(
        id="system-1",
        description="Kitchen system",
        microcontrollers=[],
    )
    microcontroller = Microcontroller(
        id="board-1",
        hardware_system_id="system-1",
        port="/dev/cu.usbserial-1140",
        baud_rate=115200,
        fqbn="arduino:avr:mega",
        connections=[
            Connection(
                id="sensor-1",
                microcontroller_id="board-1",
                name="obstacle_sensor",
                description="Obstacle sensor.",
                pins={"out": "7"},
                component_type="hw201",
            )
        ],
    )
    hardware_system.add_microcontrollers([microcontroller])
    return hardware_system


def build_streaming_hardware_system() -> HardwareSystem:
    hardware_system = HardwareSystem(
        id="system-1",
        description="Kitchen system",
        microcontrollers=[],
    )
    microcontroller = Microcontroller(
        id="board-1",
        hardware_system_id="system-1",
        port="/dev/cu.usbserial-1140",
        baud_rate=115200,
        fqbn="arduino:avr:mega",
        connections=[
            Connection(
                id="sensor-1",
                microcontroller_id="board-1",
                name="obstacle_sensor",
                description="Obstacle sensor.",
                pins={"out": "7"},
                component_type="hw201",
                database=FakeDatabase(),
            )
        ],
    )
    hardware_system.add_microcontrollers([microcontroller])
    return hardware_system


def build_led_hardware_system() -> HardwareSystem:
    hardware_system = HardwareSystem(
        id="system-1",
        description="Kitchen system",
        microcontrollers=[],
    )
    microcontroller = Microcontroller(
        id="board-1",
        hardware_system_id="system-1",
        port="/dev/cu.usbserial-1140",
        baud_rate=115200,
        fqbn="arduino:avr:mega",
        connections=[
            Connection(
                id="green-led",
                microcontroller_id="board-1",
                name="green_led",
                description="Green LED.",
                pins={"out": "13"},
                component_type="led",
            )
        ],
    )
    hardware_system.add_microcontrollers([microcontroller])
    return hardware_system


def test_register_serial_connection_caches_per_microcontroller(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.server.server.FastMCP", FakeFastMCP)
    monkeypatch.setattr("gerbera_sdk.server.server.SerialConnection", FakeSerialConnection)

    server = GerberaServer(build_hardware_system())

    server._register_serial_connection()

    assert set(server.serial_pool.keys()) == {"board-1"}
    serial_connection = server.serial_pool["board-1"]
    assert serial_connection.connect_calls == [("/dev/cu.usbserial-1140", 115200)]


def test_registered_tool_uses_cached_serial_connection(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.server.server.FastMCP", FakeFastMCP)
    monkeypatch.setattr("gerbera_sdk.server.server.SerialConnection", FakeSerialConnection)

    server = GerberaServer(build_hardware_system())
    server._register_serial_connection()

    tool = server.app.registered_tools["read_obstacle_sensor"]
    response = tool()

    serial_connection = server.serial_pool["board-1"]
    assert serial_connection.send_calls == ["READ,obstacle_sensor"]
    assert response == {"value": "1"}


def test_close_destroys_registered_serial_connections(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.server.server.FastMCP", FakeFastMCP)
    monkeypatch.setattr("gerbera_sdk.server.server.SerialConnection", FakeSerialConnection)

    server = GerberaServer(build_hardware_system())
    server._register_serial_connection()
    serial_connection = server.serial_pool["board-1"]

    server.close()

    assert serial_connection.destroy_called is True
    assert server.serial_pool == {}


def test_stream_toggle_tools_send_state_commands(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.server.server.FastMCP", FakeFastMCP)
    monkeypatch.setattr("gerbera_sdk.server.server.SerialConnection", FakeSerialConnection)

    server = GerberaServer(build_streaming_hardware_system())
    server._register_serial_connection()

    turn_on = server.app.registered_tools["turn_on_obstacle_sensor_stream"]
    turn_off = server.app.registered_tools["turn_off_obstacle_sensor_stream"]

    assert turn_on() == {"value": "1"}
    assert turn_off() == {"value": "1"}

    serial_connection = server.serial_pool["board-1"]
    assert serial_connection.send_calls == [
        "WRITE,obstacle_sensor,state:on",
        "WRITE,obstacle_sensor,state:off",
    ]

    server.close()


def test_state_toggle_tools_send_state_commands(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.server.server.FastMCP", FakeFastMCP)
    monkeypatch.setattr("gerbera_sdk.server.server.SerialConnection", FakeSerialConnection)

    server = GerberaServer(build_led_hardware_system())
    server._register_serial_connection()

    turn_on = server.app.registered_tools["turn_on_green_led"]
    turn_off = server.app.registered_tools["turn_off_green_led"]

    assert turn_on() == {"value": "1"}
    assert turn_off() == {"value": "1"}

    serial_connection = server.serial_pool["board-1"]
    assert serial_connection.send_calls == [
        "WRITE,green_led,state:on",
        "WRITE,green_led,state:off",
    ]

    server.close()
