import asyncio
import json
from types import SimpleNamespace

from fastmcp import FastMCP
import pytest

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
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
        self.on_write = lambda: None

    def write(self, command: str) -> None:
        self.commands.append(command)
        self.on_write()


def test_server_registers_named_camera_tools_when_camera_exists() -> None:
    camera = Camera(
        id="local-camera",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
    )
    captured_batches = []
    started_streams = []
    stopped_streams = []
    camera_output = VisionLanguageModelFrameEnvironment(
        environment_name="workshop",
        description="A workbench",
        objects=[],
    )
    camera_runtime = SimpleNamespace(
        capture_frames=lambda **kwargs: (
            captured_batches.append(kwargs)
        ),
        get_camera_session=lambda camera_key: SimpleNamespace(
            camera=SimpleNamespace(latest_output=camera_output)
        ),
        turn_on_camera_stream=lambda camera_key, running_models: (
            started_streams.append((camera_key, running_models))
        ),
        turn_off_camera_stream=lambda camera_key: (
            stopped_streams.append(camera_key)
        ),
    )
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(cameras=[camera]),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
        camera_runtime=camera_runtime,
    )

    GerberaRuntime._register_server_runtime_tools(runtime)
    result = app.tools["capture_frames_from_local_camera"](
        ["openai-vision-language-model"],
        3,
        0.25,
    )

    assert captured_batches == [
        {
            "camera_key": "local-camera",
            "running_models": {
                "openai-vision-language-model": True,
            },
            "image_count": 3,
            "interval_seconds": 0.25,
        }
    ]
    assert json.loads(result) == camera_output.model_dump()

    assert app.tools["turn_on_local_camera_stream"](
        ["openai-vision-language-model"],
    ) is None
    assert started_streams == [
        (
            "local-camera",
            {"openai-vision-language-model": True},
        )
    ]

    assert app.tools["turn_off_local_camera_stream"]() is None
    assert stopped_streams == ["local-camera"]


def test_fastmcp_camera_capture_schema_exposes_batch_controls() -> None:
    model = SimpleNamespace(
        name="openai-vision-language-model",
        description="Analyze supplied images.",
        predict_with_base64=lambda frames: None,
    )
    camera = Camera(
        id="local-camera",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
        subscribed_models=[model],
    )
    camera_runtime = SimpleNamespace(
        capture_frames=lambda **kwargs: None,
        get_camera_session=lambda camera_key: SimpleNamespace(
            camera=SimpleNamespace(latest_output=None)
        ),
        turn_on_camera_stream=lambda camera_key, running_models: None,
        turn_off_camera_stream=lambda camera_key: None,
    )
    event_bus = EventBus()
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(cameras=[camera]),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
        camera_runtime=camera_runtime,
    )

    GerberaRuntime._register_server_runtime_tools(runtime)
    tool = asyncio.run(app.get_tool("capture_frames_from_local_camera"))
    predict_tool = asyncio.run(
        app.get_tool("predict_with_openai-vision-language-model")
    )
    properties = tool.parameters["properties"]

    assert asyncio.run(app.get_tool("capture_from_local_camera")) is None
    assert properties["image_count"] == {
        "default": 1,
        "maximum": 20,
        "minimum": 1,
        "type": "integer",
    }
    assert properties["interval_seconds"] == {
        "default": 0.0,
        "maximum": 60.0,
        "minimum": 0.0,
        "type": "number",
    }
    assert predict_tool.parameters["properties"]["frames"] == {
        "items": {"type": "string"},
        "type": "array",
    }


def test_server_registers_model_base64_prediction_as_a_tool() -> None:
    prediction = VisionLanguageModelFrameEnvironment(
        environment_name="workshop",
        description="A workbench",
        objects=[],
    )
    received_frames = []
    model = SimpleNamespace(
        name="openai-vision-language-model",
        description="Analyze supplied images.",
        predict_with_base64=lambda frames: (
            received_frames.append(frames) or prediction
        ),
    )
    camera = Camera(
        id="local-camera",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
        subscribed_models=[model],
    )
    camera_runtime = SimpleNamespace(
        capture_frames=lambda **kwargs: None,
        get_camera_session=lambda camera_key: SimpleNamespace(
            camera=SimpleNamespace(latest_output=None)
        ),
        turn_on_camera_stream=lambda camera_key, running_models: None,
        turn_off_camera_stream=lambda camera_key: None,
    )
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(cameras=[camera]),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
        camera_runtime=camera_runtime,
    )

    GerberaRuntime._register_server_runtime_tools(runtime)
    result = app.tools["predict_with_openai-vision-language-model"](
        ["first-base64", "second-base64"]
    )

    assert received_frames == [["first-base64", "second-base64"]]
    assert result is prediction


def test_server_does_not_register_capture_frame_without_cameras() -> None:
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
    )

    GerberaRuntime._register_server_runtime_tools(runtime)

    assert {
        "capture_frames_from_local_camera",
        "turn_on_local_camera_stream",
        "turn_off_local_camera_stream",
    }.isdisjoint(app.tools)


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
    event = event_bus.get_handler(
        ("MCP", board.id, board.connections[0].event_name)
    )
    serial_connection.on_write = lambda: event.perform_work({"state": "on"})
    response = app.tools["turn_on_status_led"]()

    assert response == {"state": "on"}
    assert serial_connection.commands == ["WRITE,status_led,state:on"]
    assert set(app.tools) == {
        "write_status_led",
        "turn_on_status_led",
        "turn_off_status_led",
    }


def test_streaming_sensor_exposes_only_read_and_stream_controls(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    database = Database(
        "localhost",
        5432,
        "user",
        "password",
        "gerbera",
    )
    sensor = Connection(
        "ir_sensor",
        "hw201",
        {"out": "7"},
        database=database,
    )
    board = Microcontroller(
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
    )
    board.add_connections([sensor])
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(microcontrollers=[board]),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
    )

    GerberaRuntime._register_server_runtime_tools(runtime)

    assert set(app.tools) == {
        "read_ir_sensor",
        "turn_on_ir_sensor_stream",
        "turn_off_ir_sensor_stream",
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


def test_server_registers_agent_rule_tool(tmp_path) -> None:
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
    runtime.agent_runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=runtime.rule_bus,
        rule_buffer=runtime.rule_buffer,
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    GerberaRuntime._register_agent_runtime_tool(runtime)

    tool = asyncio.run(app.get_tool("insert_rule"))
    asyncio.run(
        tool.run(
            {
                "event_type": "STREAM",
                "microcontroller_id": "board-1",
                "event_name": "temperature",
                "expected_value": 20,
                "operator": "greater_than",
                "callback_body": "return value",
            }
        )
    )

    event_key = ("STREAM", "board-1", "temperature")
    rule = runtime.rule_bus.get_rule(event_key)
    assert rule is not None
    assert rule.condition.expected == 20.0
    assert type(rule.condition.expected) is float
    assert rule.trigger_mode.value == "repeat"
    assert event_key in runtime.rule_buffer.buffer
    assert len(list(runtime.agent_runtime.rules_path.glob("*.py"))) == 1

    delete_tool = asyncio.run(app.get_tool("delete_rule"))
    asyncio.run(
        delete_tool.run(
            {
                "event_type": "STREAM",
                "microcontroller_id": "board-1",
                "event_name": "temperature",
            }
        )
    )

    assert runtime.rule_bus.get_rule(event_key) is None
    assert event_key not in runtime.rule_buffer.buffer
    assert list(runtime.agent_runtime.rules_path.glob("*.py")) == []


def test_server_exposes_registered_events_as_nested_catalog(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    database = Database("localhost", 5432, "user", "password", "gerbera")
    connection = Connection(
        "front_distance",
        "hcsr04",
        {"trigger": "7", "echo": "8"},
        description="Distance readings from the front sensor.",
        database=database,
    )
    board = Microcontroller(
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
    )
    board.add_connections([connection])
    event_bus = EventBus()
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(microcontrollers=[board]),
        board_runtime=object(),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=app,
    )
    runtime._register_events()

    GerberaRuntime._register_event_catalog_tool(runtime)

    tool = asyncio.run(app.get_tool("list_rule_events"))
    result = asyncio.run(tool.run({}))
    catalog = result.structured_content
    expected_metadata = {
        "event_type": "MCP",
        "microcontroller_id": "board-1",
        "event_name": connection.event_name,
        "connection_name": "front_distance",
        "component_type": "hcsr04",
        "description": "Distance readings from the front sensor.",
        "streamable": False,
    }
    assert catalog["MCP"]["board-1"][connection.event_name] == (
        expected_metadata
    )

    expected_metadata["event_type"] = "STREAM"
    expected_metadata["streamable"] = True
    assert catalog["STREAM"]["board-1"][connection.event_name] == (
        expected_metadata
    )


def test_database_backed_tool_description_includes_table_name() -> None:
    database = Database("localhost", 5432, "user", "password", "gerbera")
    connection = Connection(
        "motor",
        "sg90",
        {"signal": "7"},
        database=database,
    )
    command = CommandCompiler.command_specs(connection)[0]
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=object(),
        board_runtime=object(),
        event_bus=EventBus(),
        stream_controller=object(),
        event_worker=EventWorker(),
        app=app,
    )

    runtime._register_connection_tool(connection, command)

    tool = asyncio.run(app.get_tool("write_motor"))
    assert (
        f"Collected data is stored in table `{connection.event_name}`."
        in tool.description
    )


def test_event_listener_lifecycle_is_strict() -> None:
    event_bus = EventBus()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(),
        board_runtime=SimpleNamespace(serial_pool={}),
        event_bus=event_bus,
        stream_controller=StreamController(event_bus),
        event_worker=EventWorker(),
        app=FakeApp(),
    )

    assert runtime.rule_bus.rule_bus == {}
    assert runtime.rule_buffer.buffer == {}

    with pytest.raises(RuntimeError, match="not running"):
        runtime._stop_event_listener()

    runtime._start_event_listener()
    assert runtime.event_listener is not None
    assert runtime.event_listener._rule_buffer is runtime.rule_buffer

    with pytest.raises(RuntimeError, match="already running"):
        runtime._start_event_listener()

    runtime._stop_event_listener()


def test_stream_off_waits_for_buffered_database_writes() -> None:
    calls: list[str] = []
    connection = SimpleNamespace(
        perform_action=lambda action, params: (
            calls.append("hardware.off") or {"status": "off"}
        )
    )
    stream_controller = SimpleNamespace(
        stop_stream=lambda microcontroller, stream_connection: calls.append(
            "stream.flush"
        )
    )
    event_worker = SimpleNamespace(
        wait_until_idle=lambda: calls.append("database.wait")
    )
    runtime = ServerRuntime(
        hardware_system=object(),
        board_runtime=object(),
        event_bus=EventBus(),
        stream_controller=stream_controller,
        event_worker=event_worker,
        app=FakeApp(),
    )
    tool = runtime._build_stream_toggle_tool_function(
        microcontroller=object(),
        connection=connection,
        state="off",
    )

    assert tool() == {"status": "off"}
    assert calls == [
        "hardware.off",
        "stream.flush",
        "database.wait",
    ]
