import asyncio
from datetime import datetime
from types import SimpleNamespace

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
import numpy as np
import pytest

from gerbera_sdk.contracts.tool_contract import ToolStage, stage_metadata
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.rules.rule_buffer import RuleBuffer
from gerbera_sdk.events.rules.rule_bus import RuleBus
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference import (
    Frame,
    ObjectDetectionModelInference,
    PerceptionStateModel,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime as _ServerRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


class FakeApp:
    def __init__(self) -> None:
        self.tools = {}
        self.annotations = {}
        self.metadata = {}

    def tool(
        self,
        name: str,
        description: str,
        annotations=None,
        meta=None,
    ):
        def register(function):
            self.tools[name] = function
            self.annotations[name] = annotations
            self.metadata[name] = meta
            return function

        return register


class FakeSerialConnection:
    def __init__(self) -> None:
        self.commands = []
        self.on_write = lambda: None

    def write(self, command: str) -> None:
        self.commands.append(command)
        self.on_write()


def _database() -> Database:
    return Database("localhost", 5432, "user", "password", "gerbera")


def _event_worker() -> EventWorker:
    return EventWorker(database=_database())


def ServerRuntime(**dependencies) -> _ServerRuntime:
    rule_bus = dependencies.setdefault("rule_bus", RuleBus())
    dependencies.setdefault("rule_buffer", RuleBuffer(rule_bus))
    dependencies.setdefault("agent_runtime", SimpleNamespace())
    dependencies.setdefault("event_listener", SimpleNamespace())
    return _ServerRuntime(**dependencies)


def test_server_registers_camera_capture_tool() -> None:
    camera = Camera(
        camera_id="local-camera",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
    )
    captured_batches = []
    frames = [
        SimpleNamespace(to_base64_string=lambda: "first-base64"),
        SimpleNamespace(to_base64_string=lambda: "second-base64"),
    ]
    camera_runtime = SimpleNamespace(
        capture_frames=lambda **kwargs: (
            captured_batches.append(kwargs) or frames
        ),
    )
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(cameras=[camera]),
        board_runtime=object(),
        event_bus=EventBus(),
        event_worker=_event_worker(),
        app=app,
        camera_runtime=camera_runtime,
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_hardware_tools()
    result = app.tools["capture_frames_from_local_camera"](3, 0.25)

    assert captured_batches == [
        {
            "camera_key": "local-camera",
            "image_count": 3,
            "interval_seconds": 0.25,
        }
    ]
    assert result == ["first-base64", "second-base64"]
    assert set(app.tools) == {"capture_frames_from_local_camera"}


def test_fastmcp_camera_capture_schema_exposes_batch_controls() -> None:
    camera = Camera(
        camera_id="local-camera",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
    )
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(cameras=[camera]),
        board_runtime=object(),
        event_bus=EventBus(),
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(capture_frames=lambda **kwargs: []),
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_hardware_tools()
    tool = asyncio.run(app.get_tool("capture_frames_from_local_camera"))
    properties = tool.parameters["properties"]

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
    assert tool.annotations == ToolAnnotations(
        title="Capture frames from local_camera",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    assert asyncio.run(app.get_tool("turn_on_local_camera_stream")) is None
    assert asyncio.run(app.get_tool("turn_off_local_camera_stream")) is None


def test_server_registers_model_base64_prediction_as_a_tool() -> None:
    prediction = VisionLanguageModelFrameEnvironment(
        environment_name="workshop",
        description="A workbench",
        objects=[],
    )
    received_frames = []
    received_model_ids = []
    read_calls = []
    model = SimpleNamespace(
        name="openai-vision-language-model",
        description="Analyze supplied images.",
        predict=lambda frames: (
            received_frames.append(frames) or prediction
        ),
    )
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(models=[SimpleNamespace()]),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(
            model_inferences={"vision-id": model},
            single_inference=lambda model_id, frames: (
                received_model_ids.append(model_id)
                or model.predict(frames)
            ),
            read_model_output=lambda model_id, camera_id: (
                read_calls.append((model_id, camera_id)) or prediction
            ),
            turn_on_model=lambda model_id: (
                model.turn_on_prediction_loop()
            ),
            turn_off_model=lambda model_id: (
                model.turn_off_prediction_loop()
            ),
        ),
    )

    runtime._register_hardware_tools()
    result = app.tools["perform_single_openai-vision-language-model"](
        ["first-base64", "second-base64"]
    )
    latest_result = app.tools["read_openai-vision-language-model"](
        "camera-id"
    )

    assert received_frames == [["first-base64", "second-base64"]]
    assert received_model_ids == ["vision-id"]
    assert result is prediction
    assert read_calls == [("vision-id", "camera-id")]
    assert latest_result is prediction
    assert app.annotations[
        "perform_single_openai-vision-language-model"
    ].openWorldHint is True
    assert app.annotations[
        "read_openai-vision-language-model"
    ].readOnlyHint is True
    assert app.metadata[
        "turn_on_openai-vision-language-model"
    ] == stage_metadata(ToolStage.OBSERVATION)
    assert app.metadata[
        "turn_off_openai-vision-language-model"
    ] == stage_metadata(ToolStage.OBSERVATION)


def test_server_registers_single_object_detection_as_a_tool() -> None:
    camera = Camera(
        camera_id="camera-id",
        name="local_camera",
        description="Local camera",
        source=DeviceCameraSource(device_index=0),
    )
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )
    prediction = PerceptionStateModel(
        camera_id="camera-id",
        frame=frame,
        model_name="local_object_detection_model",
        perception_objects=[],
    )
    inference = ObjectDetectionModelInference(
        model_session=SimpleNamespace(_thread=None, _stop_event=None),
        name="local_object_detection_model",
        description="Detect parts.",
        subscribed_cameras=[camera],
    )
    received_calls = []
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(models=[SimpleNamespace()]),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(
            model_inferences={"detector-id": inference},
            single_inference=lambda model_id, camera_ids: (
                received_calls.append((model_id, camera_ids))
                or [prediction]
            ),
            read_model_output=lambda model_id, camera_id: prediction,
            turn_on_model=lambda model_id: None,
            turn_off_model=lambda model_id: None,
        ),
    )

    runtime._register_hardware_tools()
    result = app.tools["perform_single_local_object_detection_model"](
        ["camera-id"]
    )
    latest_result = app.tools["read_local_object_detection_model"](
        "camera-id"
    )
    catalog = app.tools["list_configured_models"]()

    assert received_calls == [("detector-id", ["camera-id"])]
    expected_result = {
        "camera_id": "camera-id",
        "model_name": "local_object_detection_model",
        "perception_objects": [],
    }
    assert result == [expected_result]
    assert latest_result == expected_result
    assert [entry.model_dump() for entry in catalog] == [
        {
            "model_id": "detector-id",
            "name": "local_object_detection_model",
            "description": "Detect parts.",
            "model_type": "object_detection",
            "subscribed_cameras": [
                {
                    "camera_id": "camera-id",
                    "name": "local_camera",
                }
            ],
            "is_running": False,
            "turn_on_tool": "turn_on_local_object_detection_model",
            "turn_off_tool": "turn_off_local_object_detection_model",
            "read_tool": "read_local_object_detection_model",
            "single_inference_tool": (
                "perform_single_local_object_detection_model"
            ),
        }
    ]


def test_fastmcp_object_detection_tool_uses_camera_id_input() -> None:
    inference = ObjectDetectionModelInference(
        model_session=SimpleNamespace(_thread=None, _stop_event=None),
        name="part-detector",
        description="Detect parts.",
    )
    event_bus = EventBus()
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(models=[SimpleNamespace()]),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(
            model_inferences={"detector-id": inference},
            single_inference=lambda model_id, camera_id: None,
            read_model_output=lambda model_id, camera_id: None,
            turn_on_model=lambda model_id: None,
            turn_off_model=lambda model_id: None,
        ),
    )

    runtime._register_hardware_tools()
    tool = asyncio.run(app.get_tool("perform_single_part-detector"))
    turn_on_tool = asyncio.run(app.get_tool("turn_on_part-detector"))

    assert tool.parameters["properties"] == {
        "camera_ids": {
            "items": {"type": "string"},
            "minItems": 1,
            "type": "array",
        }
    }
    assert tool.annotations == ToolAnnotations(
        title="Perform one-shot inference with part-detector",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    assert turn_on_tool.meta == stage_metadata(ToolStage.OBSERVATION)


def test_server_registers_lifecycle_tools_for_every_configured_model() -> None:
    calls = []
    vision_inference = SimpleNamespace(
        name="workspace-vlm",
        description="Observe the workspace.",
        predict=lambda frames: None,
        turn_on_prediction_loop=lambda: calls.append("vlm.on"),
        turn_off_prediction_loop=lambda: calls.append("vlm.off"),
    )
    object_detection_inference = SimpleNamespace(
        name="part-detector",
        description="Detect parts.",
        predict=lambda frames: None,
        turn_on_prediction_loop=lambda: calls.append("detector.on"),
        turn_off_prediction_loop=lambda: calls.append("detector.off"),
    )
    hardware_system = HardwareSystem(
        models=[SimpleNamespace(), SimpleNamespace()]
    )
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=hardware_system,
        board_runtime=object(),
        event_bus=EventBus(),
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(
            model_inferences={
                "vision-id": vision_inference,
                "detector-id": object_detection_inference,
            },
            turn_on_model=lambda model_id: (
                {
                    "vision-id": vision_inference,
                    "detector-id": object_detection_inference,
                }[model_id].turn_on_prediction_loop()
            ),
            turn_off_model=lambda model_id: (
                {
                    "vision-id": vision_inference,
                    "detector-id": object_detection_inference,
                }[model_id].turn_off_prediction_loop()
            ),
        ),
    )

    runtime._register_hardware_tools()

    app.tools["turn_on_workspace-vlm"]()
    app.tools["turn_on_part-detector"]()
    app.tools["turn_off_workspace-vlm"]()
    app.tools["turn_off_part-detector"]()

    assert calls == [
        "vlm.on",
        "detector.on",
        "vlm.off",
        "detector.off",
    ]


def test_server_does_not_register_camera_lifecycle_tools() -> None:
    event_bus = EventBus()
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_hardware_tools()

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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_events()
    runtime._register_hardware_tools()
    event = event_bus.get_event(
        "MCP",
        board.id,
        board.connections[0].event_name,
    )
    serial_connection.on_write = lambda: event.perform_work({"state": "1"})
    response = app.tools["turn_on_status_led"]()

    assert response == {"state": "1"}
    assert serial_connection.commands == ["WRITE,status_led,state:1.0"]
    assert set(app.tools) == {
        "write_status_led",
        "turn_on_status_led",
        "turn_off_status_led",
    }
    assert app.annotations["write_status_led"] == ToolAnnotations(
        title="Set status_led LED state",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_hardware_tools()

    assert set(app.tools) == {
        "read_ir_sensor",
        "turn_on_ir_sensor_stream",
        "turn_off_ir_sensor_stream",
    }
    assert app.annotations["read_ir_sensor"].readOnlyHint is True
    assert app.annotations["turn_on_ir_sensor_stream"].idempotentHint is True
    assert app.metadata["turn_on_ir_sensor_stream"] == stage_metadata(
        ToolStage.OBSERVATION
    )
    assert app.metadata["turn_off_ir_sensor_stream"] == stage_metadata(
        ToolStage.OBSERVATION
    )


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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )
    runtime._register_connection_tool(
        connection,
        command,
        CommandCompiler.command_annotations(connection, command),
    )

    tool = asyncio.run(app.get_tool("write_motor"))
    assert tool.description == "Set servo angle."
    assert tool.annotations == ToolAnnotations(
        title="Set motor servo angle",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
    assert tool.parameters == {
        "additionalProperties": False,
        "properties": {
            "angle": {
                "description": "Servo angle in degrees.",
                "maximum": 180,
                "minimum": 0,
                "type": "number",
            }
        },
        "required": ["angle"],
        "type": "object",
    }

    asyncio.run(tool.run({"angle": 90}))
    assert captured_params == [{"angle": 90}]

    with pytest.raises(ValueError, match="less than or equal to 180"):
        asyncio.run(tool.run({"angle": 181}))


def test_server_preserves_required_and_optional_registry_parameters() -> None:
    connection = Connection(
        "motor",
        "dcmotor",
        {"in1": "5", "in2": "6", "enable": "9"},
    )
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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )
    runtime._register_connection_tool(
        connection,
        command,
        CommandCompiler.command_annotations(connection, command),
    )

    tool = asyncio.run(app.get_tool("write_motor"))
    assert tool.parameters["required"] == ["direction"]
    assert set(tool.parameters["properties"]) == {"direction", "speed"}

    asyncio.run(tool.run({"direction": 0}))
    asyncio.run(tool.run({"direction": 1, "speed": 120}))
    assert captured_params == [
        {"direction": 0},
        {"direction": 1, "speed": 120},
    ]


def test_server_registers_agent_rule_tool(tmp_path) -> None:
    event_bus = EventBus()
    app = FastMCP("test")
    runtime = ServerRuntime(
        hardware_system=object(),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )
    runtime.agent_runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=runtime.rule_bus,
        rule_buffer=runtime.rule_buffer,
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    runtime._register_rule_tools()

    tool = asyncio.run(app.get_tool("insert_rule"))
    assert tool.annotations == ToolAnnotations(
        title="Create an event rule",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
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
    assert delete_tool.annotations.destructiveHint is True
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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )
    runtime._register_events()

    runtime._register_event_catalog_tool()

    tool = asyncio.run(app.get_tool("list_rule_events"))
    assert tool.annotations.readOnlyHint is True
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
        event_worker=_event_worker(),
        app=app,
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )

    runtime._register_connection_tool(
        connection,
        command,
        CommandCompiler.command_annotations(connection, command),
    )

    tool = asyncio.run(app.get_tool("write_motor"))
    assert (
        f"Collected data is stored in table `{connection.event_name}`."
        in tool.description
    )


def test_server_uses_prebuilt_rule_and_listener_dependencies() -> None:
    event_bus = EventBus()
    rule_bus = RuleBus()
    rule_buffer = RuleBuffer(rule_bus)
    event_listener = SimpleNamespace()
    runtime = ServerRuntime(
        hardware_system=HardwareSystem(),
        board_runtime=SimpleNamespace(serial_pool={}),
        event_bus=event_bus,
        event_worker=_event_worker(),
        app=FakeApp(),
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
        rule_bus=rule_bus,
        rule_buffer=rule_buffer,
        event_listener=event_listener,
    )

    assert runtime.rule_bus is rule_bus
    assert runtime.rule_buffer is rule_buffer
    assert runtime.event_listener is event_listener


def test_stream_off_waits_for_buffered_database_writes() -> None:
    calls: list[str] = []
    connection = SimpleNamespace(
        perform_action=lambda action, params: (
            calls.append("hardware.off") or {"status": "off"}
        )
    )
    event_bus = SimpleNamespace(
        get_event=lambda event_type, microcontroller_id, event_name: SimpleNamespace(
            flush=lambda: calls.append("stream.flush")
        )
    )
    event_worker = SimpleNamespace(
        wait_until_idle=lambda: calls.append("database.wait")
    )
    runtime = ServerRuntime(
        hardware_system=object(),
        board_runtime=object(),
        event_bus=event_bus,
        event_worker=event_worker,
        app=FakeApp(),
        camera_runtime=SimpleNamespace(),
        model_runtime=SimpleNamespace(model_inferences={}),
    )
    tool = runtime._build_stream_toggle_tool_function(
        microcontroller=object(),
        connection=connection,
        state=0,
    )

    assert tool() == {"status": "off"}
    assert calls == [
        "hardware.off",
        "stream.flush",
        "database.wait",
    ]
