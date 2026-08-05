from datetime import datetime

import numpy as np
import pytest

from gerbera_sdk.inference import (
    Frame,
    ModelOutputStore,
    ObjectDetectionModel,
    ObjectDetectionModelProviderEnum,
    PerceptionStateModel,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource


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


def test_registers_each_model_camera_pair() -> None:
    first_camera = make_camera("first")
    second_camera = make_camera("second")
    model = make_model([first_camera, second_camera])
    store = ModelOutputStore()

    store.register_models([model])

    store.check_model_registered(first_camera.camera_id, model.model_id)
    store.check_model_registered(second_camera.camera_id, model.model_id)


def test_writes_and_reads_latest_model_output() -> None:
    camera = make_camera("camera")
    model = make_model([camera])
    output = make_output(camera, model)
    store = ModelOutputStore()
    store.register_models([model])

    store.write_model_output(camera.camera_id, model.model_id, output)

    assert store.read_model_output(camera.camera_id, model.model_id) is output


def test_read_fails_before_model_produces_output() -> None:
    camera = make_camera("camera")
    model = make_model([camera])
    store = ModelOutputStore()
    store.register_models([model])

    with pytest.raises(RuntimeError, match="has not produced an output"):
        store.read_model_output(camera.camera_id, model.model_id)


def test_unregistered_model_output_fails_loudly() -> None:
    store = ModelOutputStore()

    with pytest.raises(KeyError, match="not registered"):
        store.read_model_output("camera", "model")


def test_duplicate_registration_does_not_replace_existing_output() -> None:
    camera = make_camera("camera")
    model = make_model([camera])
    output = make_output(camera, model)
    store = ModelOutputStore()
    store.register_models([model])
    store.write_model_output(camera.camera_id, model.model_id, output)

    with pytest.raises(KeyError, match="already registered"):
        store.register_models([model])

    assert store.read_model_output(camera.camera_id, model.model_id) is output
