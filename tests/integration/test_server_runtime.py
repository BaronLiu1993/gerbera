from datetime import datetime
from types import SimpleNamespace

from mcp.types import ToolAnnotations
import numpy as np
import pytest

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.inference import (
    Frame,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


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


def make_server(
    *,
    hardware_system: HardwareSystem | None = None,
    camera_runtime=None,
    model_runtime=None,
    event_bus=None,
    event_worker=None,
    hardware_runtime=None,
) -> tuple[ServerRuntime, FakeApp]:
    app = FakeApp()
    runtime = ServerRuntime(
        hardware_system=hardware_system or HardwareSystem(name="test"),
        board_runtime=SimpleNamespace(),
        event_bus=event_bus or EventBus(),
        event_worker=event_worker or SimpleNamespace(
            write_to_db=lambda table_name, batch: None,
            wait_until_idle=lambda: None,
        ),
        app=app,
        camera_runtime=camera_runtime or SimpleNamespace(),
        model_runtime=model_runtime or SimpleNamespace(registered_models={}),
        event_listener=SimpleNamespace(),
        reaction_bus=ReactionBus(),
        hardware_runtime=hardware_runtime or HardwareRuntime(),
    )
    return runtime, app


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
    runtime, app = make_server(
        hardware_system=HardwareSystem(name="test", cameras=[camera]),
        camera_runtime=camera_runtime,
    )

    runtime.register_camera_tools()
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
def test_event_registration_respects_explicit_stream_flag(stream: bool) -> None:
    connection = Connection(
        name="sensor",
        component_type="hw201",
        pins={"out": "7"},
        description="Infrared sensor",
        microcontroller_id="board-1",
        stream=stream,
    )
    board = SimpleNamespace(id="board-1", connections=[connection])
    event_bus = EventBus()
    runtime, _ = make_server(
        hardware_system=HardwareSystem(
            name="test",
            microcontrollers=[board],
        ),
        event_bus=event_bus,
    )

    runtime.register_events()

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
    runtime, app = make_server(model_runtime=model_runtime)

    runtime.register_object_detection_tools(inference.model_id, inference)
    result = app.tools["perform_single_detector"]()

    assert calls == [{"model_id": inference.model_id}]
    assert result == {
        "camera_id": camera.camera_id,
        "model_name": inference.name,
        "perception_objects": [],
    }


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

    runtime, app = make_server(
        model_runtime=SimpleNamespace(
            locate_objects=locate_objects,
            analyze_scene=analyze_scene,
            read_model_output=lambda model_id, output_name: (
                "A workshop" if output_name == "scene_analysis" else objects
            ),
        )
    )

    runtime.register_vision_language_model_tools(
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

    runtime, app = make_server(
        model_runtime=SimpleNamespace(analyze_scene=analyze_scene)
    )
    runtime.register_vision_language_model_tools(
        inference.model_id,
        inference,
    )

    with pytest.raises(TypeError, match="invalid output"):
        app.tools["analyse_scene_observer"]("Describe", ["frame"])


def test_state_tools_register_runtime_bound_methods() -> None:
    hardware_runtime = HardwareRuntime(
        state_store={"hardware-key": None},
    )
    hardware_system = HardwareSystem(name="test")
    model_runtime = ModelRuntime(
        hardware_system=hardware_system,
        camera_runtime=CameraRuntime(hardware_system),
        model_outputs={"model-key": None},
    )
    runtime, app = make_server(
        hardware_runtime=hardware_runtime,
        model_runtime=model_runtime,
    )

    runtime.register_hardware_state_tool()
    runtime.register_environment_state_tool()

    assert app.tools["get_current_hardware_state"]() == {
        "hardware-key": None
    }
    assert app.tools["get_current_environment_state"]() == {
        "model-key": None
    }


def test_stream_shutdown_flushes_before_waiting_and_updates_state() -> None:
    calls: list[str] = []
    connection = SimpleNamespace(
        event_name="stream-event",
        perform_action=lambda action, params: (
            calls.append("hardware.off") or {"success": True}
        ),
    )
    event_bus = SimpleNamespace(
        get_event=lambda *args: SimpleNamespace(
            flush=lambda: calls.append("stream.flush")
        )
    )
    event_worker = SimpleNamespace(
        wait_until_idle=lambda: calls.append("database.wait")
    )
    hardware_runtime = HardwareRuntime()
    hardware_runtime.register_state_store("stream-state")
    runtime, _ = make_server(
        event_bus=event_bus,
        event_worker=event_worker,
        hardware_runtime=hardware_runtime,
    )
    tool = runtime.build_toggle_tool_function(
        connection=connection,
        state=0,
        state_key="stream-state",
        stream_microcontroller=SimpleNamespace(id="board-1"),
    )

    assert tool() == {"success": True}
    assert calls == ["hardware.off", "stream.flush", "database.wait"]
    assert hardware_runtime.get_state_store() == {
        "stream-state": {"value": "0", "unit": None}
    }
