from datetime import datetime
import time
from types import SimpleNamespace

import numpy as np
import pytest

from gerbera_sdk.inference import Frame
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime


class ObjectDetectionAdapter:
    def detect(self, frame: Frame) -> list:
        return []


class VisionLanguageAdapter:
    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    def convert_to_valid_input(self, frame: str) -> dict[str, str]:
        return {"frame": frame}

    def predict(self, **kwargs) -> dict[str, object]:
        self.user_prompts.append(kwargs["user_prompt"])
        return {
            "environment_name": "workshop",
            "description": "A workshop",
            "objects": [],
        }

    def analyze_scene(self, **kwargs) -> str:
        return "A workshop scene"


class ModelConfig:
    def __init__(self, inference) -> None:
        self.model_id = inference.model_id
        self.inference = inference

    def model_output_keys(self) -> dict[str, str]:
        return self.inference.model_output_keys

    def create_inference(self):
        return self.inference


def make_camera() -> Camera:
    return Camera(
        camera_id="camera",
        name="camera",
        description="Test camera",
        source=DeviceCameraSource(device_index=0),
    )


def make_frame() -> Frame:
    return Frame(
        timestamp=datetime.now(),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )


def make_object_detection(camera: Camera) -> ObjectDetectionModelInference:
    return ObjectDetectionModelInference(
        model=ObjectDetectionAdapter(),
        name="detector",
        description="Detect objects",
        subscribed_camera=camera,
        model_id="detector-id",
        model_output_keys={"object_detection": "detection-key"},
        interval_seconds=0.01,
    )


def make_vision(camera: Camera) -> VisionLanguageModelInference:
    return VisionLanguageModelInference(
        model=VisionLanguageAdapter(),
        name="vision",
        description="Analyze scenes",
        user_prompt="Observe the scene",
        subscribed_camera=camera,
        model_id="vision-id",
        model_output_keys={
            "locate_object": "objects-key",
            "scene_analysis": "analysis-key",
        },
        interval_seconds=0.01,
    )


def make_runtime(*inferences) -> ModelRuntime:
    cameras = {
        inference.subscribed_camera.camera_id: inference.subscribed_camera
        for inference in inferences
    }
    hardware_system = HardwareSystem(
        name="test",
        cameras=list(cameras.values()),
        models=[ModelConfig(inference) for inference in inferences],
    )
    camera_runtime = CameraRuntime(hardware_system)
    camera_runtime.build_camera_sessions()
    for camera_id in cameras:
        camera_runtime.latest_frames[camera_id] = make_frame()
    runtime = ModelRuntime(hardware_system, camera_runtime)
    runtime.register_models()
    return runtime


def test_register_models_creates_each_output_slot() -> None:
    camera = make_camera()
    runtime = make_runtime(
        make_object_detection(camera),
        make_vision(camera),
    )

    assert runtime.model_outputs == {
        "detection-key": None,
        "objects-key": None,
        "analysis-key": None,
    }


def test_register_models_rejects_duplicate_model_ids() -> None:
    camera = make_camera()
    first = make_object_detection(camera)
    second = make_object_detection(camera)
    hardware_system = HardwareSystem(
        name="test",
        cameras=[camera],
        models=[ModelConfig(first), ModelConfig(second)],
    )
    runtime = ModelRuntime(hardware_system, CameraRuntime(hardware_system))

    with pytest.raises(ValueError, match="Duplicate model ID"):
        runtime.register_models()


def test_register_models_rejects_registration_while_streaming() -> None:
    camera = make_camera()
    inference = make_object_detection(camera)
    runtime = make_runtime(inference)
    runtime.model_streams[inference.model_id] = SimpleNamespace()

    with pytest.raises(RuntimeError, match="streams are active"):
        runtime.register_models()


def test_read_fails_before_output_is_produced() -> None:
    camera = make_camera()
    inference = make_object_detection(camera)
    runtime = make_runtime(inference)

    with pytest.raises(RuntimeError, match="has not been produced yet"):
        runtime.read_model_output(inference.model_id, "object_detection")


def test_object_detection_uses_its_subscribed_camera() -> None:
    camera = make_camera()
    inference = make_object_detection(camera)
    runtime = make_runtime(inference)

    result = runtime.perform_object_detection(inference.model_id)

    assert result.camera_id == camera.camera_id


def test_vlm_operations_persist_their_outputs() -> None:
    camera = make_camera()
    inference = make_vision(camera)
    runtime = make_runtime(inference)

    objects = runtime.locate_objects(
        inference.model_id,
        ["encoded-frame"],
        "Locate objects",
    )
    analysis = runtime.analyze_scene(
        inference.model_id,
        ["encoded-frame"],
        "Describe the scene",
    )

    assert runtime.read_model_output(inference.model_id, "locate_object") is objects
    assert (
        runtime.read_model_output(inference.model_id, "scene_analysis")
        == analysis
    )


@pytest.mark.parametrize(
    "operation",
    ["locate_objects", "analyze_scene"],
)
def test_vlm_operations_reject_empty_frame_batches(
    operation: str,
) -> None:
    camera = make_camera()
    inference = make_vision(camera)
    runtime = make_runtime(inference)

    with pytest.raises(ValueError, match="At least one frame"):
        getattr(runtime, operation)(inference.model_id, [], "prompt")


def test_model_stream_lifecycle_fails_on_duplicate_operations() -> None:
    camera = make_camera()
    inference = make_object_detection(camera)
    runtime = make_runtime(inference)

    runtime.turn_on_model_stream(inference.model_id)
    with pytest.raises(RuntimeError, match="already running"):
        runtime.turn_on_model_stream(inference.model_id)

    runtime.turn_off_model_stream(inference.model_id)
    with pytest.raises(RuntimeError, match="not running"):
        runtime.turn_off_model_stream(inference.model_id)


def test_turn_off_model_stream_rejects_worker_that_does_not_stop() -> None:
    camera = make_camera()
    inference = make_object_detection(camera)
    runtime = make_runtime(inference)
    stop_event = SimpleNamespace(set=lambda: None)
    runtime.model_streams[inference.model_id] = SimpleNamespace(
        stop_event=stop_event,
        thread=SimpleNamespace(
            join=lambda timeout: None,
            is_alive=lambda: True,
        ),
    )

    with pytest.raises(RuntimeError, match="did not stop"):
        runtime.turn_off_model_stream(inference.model_id)


def test_turn_on_all_model_streams_rolls_back_started_models(
    monkeypatch,
) -> None:
    camera = make_camera()
    first = make_object_detection(camera)
    second = make_vision(camera)
    runtime = make_runtime(first, second)
    started: list[str] = []
    stopped: list[str] = []

    def start(model_id: str, prompt: str | None = None) -> None:
        if model_id == second.model_id:
            raise RuntimeError("second model failed")
        started.append(model_id)

    monkeypatch.setattr(runtime, "turn_on_model_stream", start)
    monkeypatch.setattr(
        runtime,
        "turn_off_model_stream",
        lambda model_id: stopped.append(model_id),
    )

    with pytest.raises(RuntimeError, match="second model failed"):
        runtime.turn_on_all_model_streams()

    assert started == [first.model_id]
    assert stopped == [first.model_id]


def test_turn_on_all_model_streams_uses_configured_vlm_prompt() -> None:
    camera = make_camera()
    object_detection = make_object_detection(camera)
    vision = make_vision(camera)
    runtime = make_runtime(object_detection, vision)

    runtime.turn_on_all_model_streams()
    for _ in range(100):
        if (
            runtime.model_outputs["detection-key"] is not None
            and runtime.model_outputs["objects-key"] is not None
        ):
            break
        time.sleep(0.005)
    runtime.turn_off_all_model_streams()

    assert runtime.model_outputs["detection-key"] is not None
    assert runtime.model_outputs["objects-key"] is not None
    assert vision.model.user_prompts[0] == vision.user_prompt
    assert runtime.model_streams == {}
