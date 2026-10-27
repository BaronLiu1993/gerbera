from datetime import datetime
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from gerbera_sdk.inference import (
    DepthMapModel,
    Frame,
    ObjectDepthModel,
    ObjectDepthModelInference,
    ObjectDetectionModel,
    ObjectDetectionModelInference,
    ObjectSegmentationModel,
    ObjectSegmentationModelInference,
    VisionLanguageModel,
    VisionLanguageModelInference,
    VisionLanguageModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime

MODEL_TYPES = {
    "object_detection": (ObjectDetectionModel, ObjectDetectionModelInference),
    "object_depth": (ObjectDepthModel, ObjectDepthModelInference),
    "object_segmentation": (ObjectSegmentationModel, ObjectSegmentationModelInference),
    "vision_language_model": (VisionLanguageModel, VisionLanguageModelInference),
}


class VisionAdapter:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def convert_to_valid_input(self, frame: str) -> dict[str, str]:
        return {"frame": frame}

    def predict(self, **arguments) -> dict[str, object]:
        self.prompts.append(arguments["user_prompt"])
        return {"environment_name": "workshop", "description": "A workshop", "objects": []}

    def analyze_scene(self, **arguments) -> str:
        return "A workshop scene"


def adapter_for(kind: str) -> VisionAdapter | SimpleNamespace:
    if kind == "vision_language_model":
        return VisionAdapter()
    depth_map = DepthMapModel(
        width=1, height=1, values=[[1.0]], minimum_value=1.0, maximum_value=1.0,
        value_type="relative_depth", unit="relative",
    )
    return SimpleNamespace(
        detect=Mock(return_value=[]),
        segment=Mock(return_value=[]),
        estimate=Mock(return_value=depth_map),
    )


@pytest.fixture
def runtime_factory(monkeypatch):
    runtimes = []

    def build(*kinds: str) -> ModelRuntime:
        camera = Camera(
            name="camera", description="Test camera",
            source=DeviceCameraSource(0), camera_id="camera",
        )
        declarations = []
        inferences = {}
        for index, kind in enumerate(kinds):
            declaration_type, inference_type = MODEL_TYPES[kind]
            configuration = dict(model_id=f"{kind}-{index}", name=f"model_{index}", subscribed_camera=camera)
            extra = {"model_directory": kind}
            if kind == "vision_language_model":
                extra = dict(
                    model_provider=VisionLanguageModelProviderEnum.OPENAI,
                    user_prompt="Observe", api_key="test", model_name="test",
                )
            declaration = declaration_type(**configuration, **extra)
            inference_options = (
                {"user_prompt": declaration.user_prompt}
                if kind == "vision_language_model" else {}
            )
            inference = inference_type(
                **configuration, model=adapter_for(kind), description="Test model",
                model_output_keys=declaration.model_output_keys(), interval_seconds=0.01, **inference_options,
            )
            declarations.append(declaration)
            inferences[inference.model_id] = inference
            monkeypatch.setattr(declaration_type, "create_inference", lambda model: inferences[model.model_id])
        hardware = HardwareSystem(name="robot", cameras=[camera], models=declarations)
        cameras = CameraRuntime(hardware)
        cameras.build_camera_sessions()
        cameras.latest_frames[camera.camera_id] = Frame(
            timestamp=datetime.now(), image=np.zeros((2, 2, 3), dtype=np.uint8),
        )
        runtime = ModelRuntime(hardware, cameras)
        runtime.register_models()
        runtimes.append(runtime)
        return runtime

    yield build
    for runtime in runtimes:
        runtime.turn_off_all_model_streams()


def first_model(runtime: ModelRuntime):
    return next(iter(runtime.registered_models.values())).inference


@pytest.mark.parametrize("kind", ["object_detection", "object_depth", "object_segmentation"])
def test_frame_inference_persists_typed_output_for_subscribed_camera(runtime_factory, kind) -> None:
    runtime = runtime_factory(kind)
    model = first_model(runtime)
    frame = runtime.camera_runtime.get_latest_frame(model.subscribed_camera.camera_id)

    result = getattr(runtime, f"perform_{kind}")(model.model_id)

    assert (result.camera_id, runtime.read_model_output(model.model_id, kind) is result) == ("camera", True)
    assert result.frame is frame
    operation = {
        "object_detection": "detect", "object_depth": "estimate", "object_segmentation": "segment",
    }[kind]
    getattr(model.model, operation).assert_called_once_with(frame)


def test_vision_operations_persist_objects_and_scene_analysis(runtime_factory) -> None:
    runtime = runtime_factory("vision_language_model")
    model = first_model(runtime)

    objects = runtime.locate_objects(model.model_id, ["frame"], "Locate")
    description = runtime.analyze_scene(model.model_id, ["frame"], "Describe")

    assert (
        runtime.read_model_output(model.model_id, "locate_object") is objects,
        runtime.read_model_output(model.model_id, "scene_analysis"),
    ) == (True, description)


def test_registration_rejects_duplicate_model_identity(runtime_factory) -> None:
    runtime = runtime_factory("object_detection")
    runtime.hardware_system.models.append(runtime.hardware_system.models[0])

    with pytest.raises(ValueError, match="Duplicate model ID"):
        runtime.register_models()


def test_output_cannot_be_read_before_prediction(runtime_factory) -> None:
    runtime = runtime_factory("object_detection")

    with pytest.raises(RuntimeError, match="has not been produced"):
        runtime.read_model_output(first_model(runtime).model_id, "object_detection")


def test_frame_operation_rejects_vision_language_model(runtime_factory) -> None:
    runtime = runtime_factory("vision_language_model")

    with pytest.raises(TypeError, match="does not support frame inference"):
        runtime.perform_frame_inference(first_model(runtime).model_id)


def test_vision_rejects_empty_frame_batch(runtime_factory) -> None:
    runtime = runtime_factory("vision_language_model")

    with pytest.raises(ValueError, match="At least one frame"):
        runtime.locate_objects(first_model(runtime).model_id, [], "Locate")


def test_stream_lifecycle_uses_configured_prompt_and_rejects_duplicate_operations(
    runtime_factory, monkeypatch,
) -> None:
    runtime = runtime_factory("vision_language_model")
    model = first_model(runtime)
    ready = Event()
    write = runtime.write_model_output

    def record_output(key, model_output):
        write(key, model_output)
        ready.set()

    monkeypatch.setattr(runtime, "write_model_output", record_output)
    runtime.turn_on_all_model_streams()
    try:
        assert ready.wait(1)
        with pytest.raises(RuntimeError, match="already running"):
            runtime.turn_on_model_stream(model.model_id, prompt="Observe")
        with pytest.raises(RuntimeError, match="streams are active"):
            runtime.register_models()
    finally:
        runtime.turn_off_all_model_streams()
    with pytest.raises(RuntimeError, match="not running"):
        runtime.turn_off_model_stream(model.model_id)
    assert model.model.prompts[0] == model.user_prompt


def test_stream_shutdown_rejects_worker_that_does_not_stop(runtime_factory) -> None:
    runtime = runtime_factory("object_detection")
    model = first_model(runtime)
    runtime.model_streams[model.model_id] = SimpleNamespace(
        stop_event=Event(), thread=SimpleNamespace(join=lambda timeout: None, is_alive=lambda: True),
    )
    try:
        with pytest.raises(RuntimeError, match="did not stop"):
            runtime.turn_off_model_stream(model.model_id)
    finally:
        runtime.model_streams.clear()


def test_partial_stream_start_rolls_back_owned_streams(runtime_factory, monkeypatch) -> None:
    runtime = runtime_factory("object_detection", "vision_language_model")
    first, second = runtime.registered_models
    stopped = []

    def start(model_id, prompt=None):
        if model_id == second:
            raise RuntimeError("second model failed")

    monkeypatch.setattr(runtime, "turn_on_model_stream", start)
    monkeypatch.setattr(runtime, "turn_off_model_stream", lambda model_id: stopped.append(model_id))

    with pytest.raises(RuntimeError, match="second model failed"):
        runtime.turn_on_all_model_streams()

    assert stopped == [first]


def test_prediction_failure_is_reported_without_leaking_thread(runtime_factory, monkeypatch) -> None:
    runtime = runtime_factory("object_detection")
    model = first_model(runtime)
    finished = Event()
    loop = runtime.prediction_loop

    def fail(frame):
        raise ValueError("invalid prediction")

    def run(*arguments):
        try:
            loop(*arguments)
        finally:
            finished.set()

    model.model.detect = fail
    monkeypatch.setattr(runtime, "prediction_loop", run)
    runtime.turn_on_model_stream(model.model_id)
    assert finished.wait(1)
    with pytest.raises(RuntimeError, match="Model stream failed") as failure:
        runtime.read_model_output(model.model_id, "object_detection")
    assert isinstance(failure.value.__cause__, ValueError)
    assert runtime.model_streams == {}
