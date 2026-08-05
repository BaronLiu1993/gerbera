from datetime import datetime
import threading

import numpy as np
import pytest

from gerbera_sdk.inference import (
    Frame,
    ModelOutputStore,
    ObjectDetectionModel,
    ObjectDetectionModelProviderEnum,
    PerceptionStateModel,
    VisionLanguageModel,
    VisionLanguageModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime


def make_camera(name: str) -> Camera:
    return Camera(
        name=name,
        description="Test camera",
        source=DeviceCameraSource(device_index=0),
    )


def make_model(cameras: list[Camera]) -> ObjectDetectionModel:
    return ObjectDetectionModel(
        model_name=ObjectDetectionModelProviderEnum.YOLOV5,
        name="detector",
        model_source="yolov5n.onnx",
        subscribed_cameras=cameras,
    )


def make_output(camera: Camera, model: ObjectDetectionModel) -> PerceptionStateModel:
    return PerceptionStateModel(
        camera_id=camera.camera_id,
        frame=Frame(
            timestamp=datetime.now(),
            image=np.zeros((2, 2, 3), dtype=np.uint8),
        ),
        model_name=model.name,
        perception_objects=[],
    )


def register_model(store: ModelOutputStore, model: ObjectDetectionModel) -> None:
    store.register(
        [
            (camera.camera_id, model.model_id)
            for camera in model.subscribed_cameras
        ]
    )


def test_registers_each_model_camera_pair() -> None:
    first_camera = make_camera("first")
    second_camera = make_camera("second")
    store = ModelOutputStore()
    model = make_model([first_camera, second_camera])

    register_model(store, model)

    with pytest.raises(RuntimeError, match="has not produced an output"):
        store.read_model_output(first_camera.camera_id, model.model_id)

    with pytest.raises(RuntimeError, match="has not produced an output"):
        store.read_model_output(second_camera.camera_id, model.model_id)


def test_writes_and_reads_latest_model_output() -> None:
    camera = make_camera("camera")
    store = ModelOutputStore()
    model = make_model([camera])
    output = make_output(camera, model)
    register_model(store, model)

    store.write_model_output(camera.camera_id, model.model_id, output)

    assert store.read_model_output(camera.camera_id, model.model_id) is output


def test_read_fails_before_model_produces_output() -> None:
    camera = make_camera("camera")
    store = ModelOutputStore()
    model = make_model([camera])
    register_model(store, model)

    with pytest.raises(RuntimeError, match="has not produced an output"):
        store.read_model_output(camera.camera_id, model.model_id)


def test_unregistered_model_output_fails_loudly() -> None:
    store = ModelOutputStore()

    with pytest.raises(KeyError, match="not registered"):
        store.read_model_output("camera", "model")


def test_duplicate_registration_does_not_replace_existing_output() -> None:
    camera = make_camera("camera")
    store = ModelOutputStore()
    model = make_model([camera])
    output = make_output(camera, model)
    register_model(store, model)
    store.write_model_output(camera.camera_id, model.model_id, output)

    with pytest.raises(KeyError, match="already registered"):
        register_model(store, model)

    assert store.read_model_output(camera.camera_id, model.model_id) is output


def test_object_detection_runtime_receives_store_and_model_id() -> None:
    camera = make_camera("camera")
    store = ModelOutputStore()
    model = make_model([camera])

    inference = model.create_inference(store)

    assert inference.model_id == model.model_id
    assert inference.model_session.model_output_store is store


def test_vlm_runtime_receives_store_and_model_id() -> None:
    camera = make_camera("camera")
    store = ModelOutputStore()
    model = VisionLanguageModel(
        name="vision",
        model_provider=VisionLanguageModelProviderEnum.ANTHROPIC,
        user_prompt="Observe the frame",
        api_key="test-key",
        model_name="opus-4.6",
        subscribed_cameras=[camera],
    )

    inference = model.create_inference(store)

    assert inference.model_id == model.model_id
    assert inference.model_session.model_output_store is store


def test_object_detection_loop_writes_latest_output(monkeypatch) -> None:
    class FakeObjectDetectionAdapter:
        def detect(self, frame: Frame) -> list:
            return []

    camera = make_camera("camera")
    camera.latest_frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )
    store = ModelOutputStore()
    model = make_model([camera])
    register_model(store, model)
    inference = model.create_inference(store)
    inference.model_session.model = FakeObjectDetectionAdapter()
    inference.model_session._stop_event = threading.Event()

    write_model_output = store.write_model_output

    def write_then_stop(**kwargs) -> None:
        write_model_output(**kwargs)
        inference.model_session._stop_event.set()

    monkeypatch.setattr(store, "write_model_output", write_then_stop)

    inference.prediction_loop()

    output = store.read_model_output(camera.camera_id, model.model_id)
    assert isinstance(output, PerceptionStateModel)


def test_vlm_loop_writes_latest_output(monkeypatch) -> None:
    class FakeVisionLanguageModelAdapter:
        def convert_to_valid_input(self, frame: str) -> dict[str, str]:
            return {"frame": frame}

        def predict(self, **kwargs) -> dict[str, object]:
            return {
                "environment_name": "workshop",
                "description": "A workshop",
                "objects": [],
            }

    camera = make_camera("camera")
    camera.latest_frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )
    store = ModelOutputStore()
    model = VisionLanguageModel(
        name="vision",
        model_provider=VisionLanguageModelProviderEnum.ANTHROPIC,
        user_prompt="Observe the frame",
        api_key="test-key",
        model_name="opus-4.6",
        subscribed_cameras=[camera],
    )
    store.register([(camera.camera_id, model.model_id)])
    inference = model.create_inference(store)
    inference.model_session.model = FakeVisionLanguageModelAdapter()
    inference.model_session._stop_event = threading.Event()

    write_model_output = store.write_model_output

    def write_then_stop(**kwargs) -> None:
        write_model_output(**kwargs)
        inference.model_session._stop_event.set()

    monkeypatch.setattr(store, "write_model_output", write_then_stop)

    inference.prediction_loop()

    output = store.read_model_output(camera.camera_id, model.model_id)
    assert output.environment_name == "workshop"


def test_model_runtime_builds_all_model_inferences() -> None:
    camera = make_camera("camera")
    object_detection = make_model([camera])
    vision_language_model = VisionLanguageModel(
        name="vision",
        model_provider=VisionLanguageModelProviderEnum.ANTHROPIC,
        user_prompt="Observe the frame",
        api_key="test-key",
        model_name="opus-4.6",
        subscribed_cameras=[camera],
    )
    hardware_system = HardwareSystem(
        models=[object_detection, vision_language_model],
    )

    runtime = ModelRuntime(hardware_system)

    assert len(runtime.model_inferences) == 2
    for inference in runtime.model_inferences.values():
        assert (
            inference.model_session.model_output_store
            is runtime.model_output_store
        )


def test_model_runtime_starts_and_stops_all_inference_threads() -> None:
    camera = make_camera("camera")
    runtime = ModelRuntime(
        HardwareSystem(models=[make_model([camera])])
    )

    runtime.turn_on_all_models()
    assert all(
        inference.is_running
        for inference in runtime.model_inferences.values()
    )

    runtime.turn_off_all_models()
    assert all(
        not inference.is_running
        for inference in runtime.model_inferences.values()
    )


def test_model_runtime_turns_one_model_on_and_off_by_id() -> None:
    camera = make_camera("camera")
    model = make_model([camera])
    runtime = ModelRuntime(HardwareSystem(models=[model]))

    runtime.turn_on_model(model.model_id)
    runtime.turn_on_model(model.model_id)
    assert runtime.model_inferences[model.model_id].is_running

    runtime.turn_off_model(model.model_id)
    runtime.turn_off_model(model.model_id)
    assert not runtime.model_inferences[model.model_id].is_running


def test_model_runtime_runs_single_object_detection_inference_for_multiple_cameras(
) -> None:
    class FakeObjectDetectionAdapter:
        def detect(self, frame: Frame) -> list:
            return []

    cameras = [make_camera("first"), make_camera("second")]
    for camera in cameras:
        camera.latest_frame = Frame(
            timestamp=datetime.now(),
            image=np.zeros((2, 2, 3), dtype=np.uint8),
        )
    model = make_model(cameras)
    runtime = ModelRuntime(HardwareSystem(models=[model]))
    runtime.model_inferences[model.model_id].model_session.model = (
        FakeObjectDetectionAdapter()
    )

    output = runtime.single_inference(
        model.model_id,
        [camera.camera_id for camera in cameras],
    )

    assert isinstance(output, list)
    assert [result.camera_id for result in output] == [
        camera.camera_id for camera in cameras
    ]


def test_model_runtime_runs_single_vlm_inference() -> None:
    class FakeVisionLanguageModelAdapter:
        def __init__(self) -> None:
            self.frames = []

        def convert_to_valid_input(self, frame: str) -> dict[str, str]:
            self.frames.append(frame)
            return {"frame": frame}

        def predict(self, **kwargs) -> dict[str, object]:
            return {
                "environment_name": "workshop",
                "description": "A workshop",
                "objects": [],
            }

    camera = make_camera("camera")
    model = VisionLanguageModel(
        name="vision",
        model_provider=VisionLanguageModelProviderEnum.ANTHROPIC,
        user_prompt="Observe the frame",
        api_key="test-key",
        model_name="opus-4.6",
        subscribed_cameras=[camera],
    )
    runtime = ModelRuntime(HardwareSystem(models=[model]))
    adapter = FakeVisionLanguageModelAdapter()
    runtime.model_inferences[model.model_id].model_session.model = adapter

    output = runtime.single_inference(
        model.model_id,
        ["first-base64", "second-base64"],
    )

    assert output.environment_name == "workshop"
    assert adapter.frames == ["first-base64", "second-base64"]


def test_model_runtime_requires_at_least_one_object_detection_input() -> None:
    camera = make_camera("camera")
    model = make_model([camera])
    runtime = ModelRuntime(HardwareSystem(models=[model]))

    with pytest.raises(ValueError, match="At least one camera ID"):
        runtime.single_inference(model.model_id, [])
