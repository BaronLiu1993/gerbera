from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from mcp.types import ToolAnnotations
import numpy as np
import pytest

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    DeleteReactionSchema,
    ReactionActionSchema,
    ReactionConditionSchema,
    ReactionEventSchema,
    ReactionOperator,
    ReactionTriggerMode,
)
from gerbera_sdk.events.reactions.reaction_store import ReactionStore
from gerbera_sdk.inference import (
    DepthMapModel,
    Frame,
    ObjectDepthModelInference,
    ObjectDepthStateModel,
    ObjectDetectionModelInference,
    ObjectSegmentationModelInference,
    ObjectSegmentationStateModel,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeWatchdogConfig,
)
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry,
)
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.events.event_registration import EventRegistration
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_service import ReactionService
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.connection_control import ConnectionControl
from gerbera_sdk.models.runtime.server.hardware_tools import HardwareTools
from gerbera_sdk.models.runtime.server.perception_tools import PerceptionTools
from gerbera_sdk.models.runtime.server.reaction_tools import ReactionTools
from gerbera_sdk.models.runtime.server.runtime_resources import RuntimeResources
from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec


class FakeApp:
    def __init__(self) -> None:
        self.tools = {}
        self.annotations = {}

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
            return function

        return register


class ObjectDetectionAdapter:
    def detect(self, frame: Frame) -> list:
        return []


class VisionLanguageAdapter:
    def convert_to_valid_input(self, frame: str) -> dict[str, str]:
        return {"frame": frame}

    def predict(self, **kwargs) -> dict[str, object]:
        return {
            "environment_name": "workshop",
            "description": "A workshop",
            "objects": [],
        }

    def analyze_scene(self, **kwargs) -> str:
        return "A workshop"


def make_camera() -> Camera:
    return Camera(
        camera_id="camera-1",
        name="local_camera",
        description="Built-in camera",
        source=DeviceCameraSource(device_index=0),
    )


def make_frame() -> Frame:
    return Frame(
        timestamp=datetime.now(),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )


@dataclass
class ServerDependencies:
    hardware_system: HardwareSystem | None = None
    camera_runtime: object | None = None
    model_runtime: object | None = None
    event_bus: object | None = None
    event_worker: object | None = None
    hardware_runtime: HardwareRuntime | None = None
    reaction_bus: ReactionBus | None = None
    command_responses: CommandResponseRegistry | None = None


def make_server(dependencies: ServerDependencies | None = None) -> tuple[SimpleNamespace, FakeApp]:
    dependencies = dependencies or ServerDependencies()
    app = FakeApp()
    system = dependencies.hardware_system or HardwareSystem(name="test")
    plan = HardwareContractCompiler.compile(system)
    events = dependencies.event_bus or EventBus()
    worker = dependencies.event_worker or SimpleNamespace(
        write_to_db=lambda table_name, batch: None, wait_until_idle=lambda: None,
    )
    state = dependencies.hardware_runtime or HardwareRuntime()
    models = dependencies.model_runtime or SimpleNamespace(registered_models={})
    cameras = dependencies.camera_runtime or SimpleNamespace()
    responses = dependencies.command_responses or CommandResponseRegistry()
    commands = CommandExecutor(plan, SimpleNamespace(), responses)
    EventRegistration(plan, events, worker).register()
    actions = ReactionToolRegistry()
    reaction_bus = dependencies.reaction_bus or ReactionBus()
    reaction_bus.configure_executor(actions)
    tools = McpToolRegistry(app, actions)
    controls = ConnectionControl(events, worker, state, commands)
    runtime = SimpleNamespace(
        hardware_plan=plan, event_bus=events, reaction_bus=reaction_bus,
        hardware_runtime=state, commands=commands,
        hardware=HardwareTools(tools, plan, state, controls, commands),
        perception=PerceptionTools(tools, system, cameras, models),
        reactions=ReactionTools(tools, ReactionService(plan, events, reaction_bus, actions)),
        resources=RuntimeResources(tools, app, system, plan, SimpleNamespace(), state, models),
    )
    return runtime, app


def test_listener_acknowledgement_completes_server_command() -> None:
    connection = Connection(
        name="sensor",
        component_type="hw201",
        pins={"out": "7"},
        description="Infrared sensor",
        microcontroller_id="board-1",
    )
    board = Microcontroller(
        device_id="board-1",
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(100, 500),
        connections=[connection],
    )
    system = HardwareSystem(name="test", microcontrollers=[board])
    board.hardware_system_id = system.id
    registry = CommandResponseRegistry()
    runtime, _ = make_server(ServerDependencies(
        hardware_system=system,
        command_responses=registry,
    ))
    listener = EventListener(
        hardware_plan=runtime.hardware_plan,
        transport_pool={},
        event_bus=runtime.event_bus,
        reaction_bus=runtime.reaction_bus,
        hardware_runtime=runtime.hardware_runtime,
        command_responses=registry,
    )

    class AcknowledgingTransport:
        def write(self, command: str) -> None:
            message = SerialMessageCodec.decode(command)
            listener.resolve_command_response(
                {
                    "command_id": message.fields["command_id"],
                    "obstacle_detected": "1",
                }
            )

    runtime.commands.boards = SimpleNamespace(
        get_transport=lambda microcontroller_id: AcknowledgingTransport()
    )
    response = runtime.commands.execute(
        runtime.hardware_plan.boards[0].connections[0],
        "READ",
        {},
    )
    listener.reaction_executor.shutdown(wait=True)

    assert response == {
        "success": True,
        "value": {"obstacle_detected": "1"},
    }


def test_reaction_management_tools_create_list_and_delete(
    tmp_path,
) -> None:

    connection = Connection(
        name="sensor",
        component_type="hw201",
        pins={"out": "7"},
        description="Infrared sensor",
        microcontroller_id="board-1",
        stream=True,
    )
    board = Microcontroller(
        device_id="board-1",
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
        connections=[connection],
    )
    system = HardwareSystem(name="test", microcontrollers=[board])
    board.hardware_system_id = system.id
    runtime, app = make_server(ServerDependencies(
        hardware_system=system,
        reaction_bus=ReactionBus(store=ReactionStore(tmp_path)),
    ))
    resolved_board = runtime.hardware_plan.boards[0]
    resolved_connection = resolved_board.connections[0]
    runtime.hardware.register_connection_tools(resolved_connection)
    runtime.reactions.register_reaction_tools()
    request = CreateReactionSchema(
        event=ReactionEventSchema(
            event_type="STREAM",
            microcontroller_id=resolved_board.microcontroller_id,
            event_name=resolved_connection.event_name,
            payload_field="obstacle_detected",
        ),
        condition=ReactionConditionSchema(
            operator=ReactionOperator.EQUAL,
            expected_value=1,
        ),
        action=ReactionActionSchema(
            tool_name="turn_off_sensor_stream",
            arguments={},
        ),
        trigger_mode=ReactionTriggerMode.CONTINUOUS,
    )

    created = app.tools["create_reaction"](request)

    assert app.tools["list_reactions"]() == [created]
    deleted = app.tools["delete_reaction"](
        DeleteReactionSchema(
            reaction_id=created.definition.reaction_id,
        )
    )
    assert deleted.deleted == created.definition
    assert app.tools["list_reactions"]() == []


def test_camera_tool_forwards_batch_controls_and_serializes_frames() -> None:
    camera = make_camera()
    calls: list[dict[str, object]] = []
    camera_runtime = SimpleNamespace(
        capture_frames=lambda **kwargs: (
            calls.append(kwargs)
            or [
                SimpleNamespace(to_base64_string=lambda: "first"),
                SimpleNamespace(to_base64_string=lambda: "second"),
            ]
        )
    )
    runtime, app = make_server(ServerDependencies(
        hardware_system=HardwareSystem(name="test", cameras=[camera]),
        camera_runtime=camera_runtime,
    ))

    runtime.perception.register_camera_tools()
    result = app.tools["capture_frames_from_local_camera"](2, 0.25)

    assert calls == [
        {
            "camera_key": camera.camera_id,
            "image_count": 2,
            "interval_seconds": 0.25,
        }
    ]
    assert result == ["first", "second"]
    assert app.annotations["capture_frames_from_local_camera"] == (
        ToolAnnotations(
            title="Capture frames from local_camera",
            readOnlyHint=True,
            openWorldHint=False,
        )
    )


@pytest.mark.parametrize("stream", [False, True])
def test_event_registration_respects_explicit_stream_flag(
    stream: bool,
) -> None:

    connection = Connection(
        name="sensor",
        component_type="hw201",
        pins={"out": "7"},
        description="Infrared sensor",
        microcontroller_id="board-1",
        stream=stream,
    )
    board = Microcontroller(
        device_id="board-1",
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
        connections=[connection],
    )
    system = HardwareSystem(name="test", microcontrollers=[board])
    board.hardware_system_id = system.id
    event_bus = EventBus()
    runtime, _ = make_server(ServerDependencies(
        hardware_system=system,
        event_bus=event_bus,
    ))


    assert event_bus.get_event(
        "MCP",
        board.id,
        connection.event_name,
    ).streamable is False
    if stream:
        assert event_bus.get_event(
            "STREAM",
            board.id,
            connection.event_name,
        ).streamable is True
    else:
        with pytest.raises(RuntimeError, match="does not exist"):
            event_bus.get_event(
                "STREAM",
                board.id,
                connection.event_name,
            )


def test_object_detection_tools_bridge_server_and_model_runtime() -> None:
    camera = make_camera()
    inference = ObjectDetectionModelInference(
        model=ObjectDetectionAdapter(),
        name="detector",
        description="Detect objects",
        subscribed_camera=camera,
        model_id="detector-id",
    )
    output = PerceptionStateModel(
        camera_id=camera.camera_id,
        frame=make_frame(),
        model_name=inference.name,
        perception_objects=[],
    )
    calls: list[dict[str, object]] = []

    def perform_object_detection(model_id: str):
        calls.append({"model_id": model_id})
        return output

    model_runtime = SimpleNamespace(
        perform_object_detection=perform_object_detection,
        read_model_output=lambda model_id, output_name: output,
    )
    runtime, app = make_server(ServerDependencies(model_runtime=model_runtime))

    runtime.perception.register_object_detection_tools(inference.model_id, inference)
    result = app.tools["perform_single_detector"]()

    assert calls == [{"model_id": inference.model_id}]
    assert result == {
        "camera_id": camera.camera_id,
        "model_name": inference.name,
        "perception_objects": [],
    }


@pytest.mark.parametrize(
    ("inference_class", "model_name", "output_name", "output"),
    [
        (
            ObjectDepthModelInference,
            "depth",
            "object_depth",
            ObjectDepthStateModel(
                camera_id="camera-1",
                frame=make_frame(),
                model_name="depth",
                depth_map=DepthMapModel(
                    width=1,
                    height=1,
                    values=[[1.0]],
                    minimum_value=1.0,
                    maximum_value=1.0,
                    value_type="relative_depth",
                    unit="relative",
                ),
            ),
        ),
        (
            ObjectSegmentationModelInference,
            "segmenter",
            "object_segmentation",
            ObjectSegmentationStateModel(
                camera_id="camera-1",
                frame=make_frame(),
                model_name="segmenter",
                segmented_objects=[],
            ),
        ),
    ],
)
def test_frame_model_tools_bridge_server_and_model_runtime(
    inference_class,
    model_name: str,
    output_name: str,
    output,
) -> None:
    camera = make_camera()
    inference = inference_class(
        model=object(),
        name=model_name,
        description=f"Run {model_name}",
        subscribed_camera=camera,
        model_id=f"{model_name}-id",
    )
    calls: list[tuple[str, str]] = []
    model_runtime = SimpleNamespace(
        read_model_output=lambda model_id, requested_output: (
            calls.append((model_id, requested_output)) or output
        ),
        perform_frame_inference=lambda model_id: (
            calls.append((model_id, "perform")) or output
        ),
    )
    runtime, app = make_server(ServerDependencies(model_runtime=model_runtime))

    runtime.perception.register_frame_model_tools(inference.model_id, inference)
    read_result = app.tools[f"read_{model_name}"]()
    perform_result = app.tools[f"perform_single_{model_name}"]()

    assert calls == [
        (inference.model_id, output_name),
        (inference.model_id, "perform"),
    ]
    serialized_output = output.model_dump(mode="json", exclude={"frame"})
    assert read_result == serialized_output
    assert perform_result == serialized_output


def test_vision_language_tools_route_each_operation() -> None:
    camera = make_camera()
    inference = VisionLanguageModelInference(
        model=VisionLanguageAdapter(),
        name="observer",
        description="Observe scenes",
        user_prompt="Observe",
        subscribed_camera=camera,
        model_id="observer-id",
    )
    objects = VisionLanguageModelFrameEnvironment(
        environment_name="workshop",
        description="A workshop",
        objects=[],
    )
    calls: list[dict[str, object]] = []

    def locate_objects(**kwargs):
        calls.append(kwargs)
        return objects

    def analyze_scene(**kwargs):
        calls.append(kwargs)
        return "A workshop"

    runtime, app = make_server(ServerDependencies(
        model_runtime=SimpleNamespace(
            locate_objects=locate_objects,
            analyze_scene=analyze_scene,
            read_model_output=lambda model_id, output_name: (
                "A workshop" if output_name == "scene_analysis" else objects
            ),
        )
    ))

    runtime.perception.register_vision_language_model_tools(
        inference.model_id,
        inference,
    )
    captured = app.tools["capture_scene_objects_observer"](
        "Locate tools",
        ["frame"],
    )
    analysis = app.tools["analyse_scene_observer"](
        "Describe",
        ["frame"],
    )

    assert captured is objects
    assert analysis == "A workshop"
    assert calls == [
        {
            "model_id": inference.model_id,
            "frames": ["frame"],
            "prompt": "Locate tools",
        },
        {
            "model_id": inference.model_id,
            "frames": ["frame"],
            "prompt": "Describe",
        },
    ]


def test_scene_analysis_tool_hard_fails_on_non_text_output() -> None:
    camera = make_camera()
    inference = VisionLanguageModelInference(
        model=VisionLanguageAdapter(),
        name="observer",
        description="Observe scenes",
        user_prompt="Observe",
        subscribed_camera=camera,
    )

    def analyze_scene(**kwargs):
        raise TypeError("Scene analysis inference returned an invalid output")

    runtime, app = make_server(ServerDependencies(
        model_runtime=SimpleNamespace(analyze_scene=analyze_scene)
    ))
    runtime.perception.register_vision_language_model_tools(
        inference.model_id,
        inference,
    )

    with pytest.raises(TypeError, match="invalid output"):
        app.tools["analyse_scene_observer"]("Describe", ["frame"])


def test_state_tools_register_runtime_bound_methods() -> None:
    hardware_runtime = HardwareRuntime(
        state_store={("board-1", "sensor", "value"): None},
    )
    hardware_system = HardwareSystem(name="test")
    model_runtime = ModelRuntime(
        hardware_system=hardware_system,
        camera_runtime=CameraRuntime(hardware_system),
        model_outputs={"model-key": None},
    )
    runtime, app = make_server(ServerDependencies(
        hardware_runtime=hardware_runtime,
        model_runtime=model_runtime,
    ))

    runtime.resources.register_hardware_state_tool()
    runtime.resources.register_environment_state_tool()

    assert app.tools["get_current_hardware_state"]() == {
        "board-1.sensor.value": None
    }
    assert app.tools["get_current_environment_state"]() == {
        "model-key": None
    }


def test_stream_shutdown_flushes_before_waiting_and_updates_state() -> None:
    calls: list[str] = []
    connection = SimpleNamespace(
        name="sensor", component_type="hw201", microcontroller_id="board-1",
        event_name="stream-event",
    )
    event_bus = SimpleNamespace(
        get_event=lambda *args: SimpleNamespace(flush=lambda: calls.append("stream.flush")),
    )
    worker = SimpleNamespace(wait_until_idle=lambda: calls.append("database.wait"))
    state = HardwareRuntime()
    state.register_state_store(("board-1", "sensor", "stream_enabled"))
    commands = SimpleNamespace(execute=lambda *args: calls.append("hardware.off") or {"success": True})
    controls = ConnectionControl(event_bus, worker, state, commands)

    response = controls.set_stream_state(connection, 0)

    assert (response, calls, state.get_state_store()) == (
        {"success": True}, ["hardware.off", "stream.flush", "database.wait"],
        {"board-1.sensor.stream_enabled": {"value": "0", "unit": None}},
    )
