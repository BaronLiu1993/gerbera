from pathlib import Path

import pytest
import yaml

from gerbera_sdk.inference.models.neural_network import local_model_files
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_adapter import (
    DepthAnythingModelAdapter,
    MidasModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_inference import (
    ObjectDepthModel,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_adapter import (
    Yolov5SegModelAdapter,
    Yolov8SegModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_inference import (
    ObjectSegmentationModel,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource


CAMERA = Camera(
    name="camera",
    description="Test camera",
    source=DeviceCameraSource(device_index=0),
)


def write_model_directory(
    models_path: Path,
    directory_name: str,
    manifest: dict[str, object],
) -> None:
    model_directory = models_path / directory_name
    model_directory.mkdir()
    (model_directory / "model.yaml").write_text(yaml.safe_dump(manifest))
    (model_directory / "model.onnx").touch()


@pytest.mark.parametrize(
    ("model_format", "adapter_class"),
    [
        ("midas", MidasModelAdapter),
        ("depth_anything", DepthAnythingModelAdapter),
    ],
)
def test_depth_manifest_selects_adapter(
    tmp_path: Path,
    monkeypatch,
    model_format: str,
    adapter_class: type,
) -> None:
    monkeypatch.setattr(local_model_files, "MODELS_PATH", tmp_path)
    write_model_directory(
        tmp_path,
        "depth",
        {
            "schema_version": 1,
            "model_format": model_format,
            "weights": "model.onnx",
            "input": {"width": 256, "height": 256},
            "output": {
                "value_type": "relative_depth",
                "unit": "relative",
            },
        },
    )

    inference = ObjectDepthModel(
        name="depth",
        model_directory="depth",
        subscribed_camera=CAMERA,
    ).create_inference()

    assert isinstance(inference.model, adapter_class)


@pytest.mark.parametrize(
    ("model_format", "adapter_class"),
    [
        ("yolov5_seg", Yolov5SegModelAdapter),
        ("yolov8_seg", Yolov8SegModelAdapter),
    ],
)
def test_segmentation_manifest_selects_adapter(
    tmp_path: Path,
    monkeypatch,
    model_format: str,
    adapter_class: type,
) -> None:
    monkeypatch.setattr(local_model_files, "MODELS_PATH", tmp_path)
    write_model_directory(
        tmp_path,
        "segmenter",
        {
            "schema_version": 1,
            "model_format": model_format,
            "weights": "model.onnx",
            "input": {"width": 640, "height": 640},
            "output": {
                "prediction_output_name": "predictions",
                "prototype_output_name": "prototypes",
                "class_names": ["object"],
                "mask_coefficient_count": 32,
            },
        },
    )

    inference = ObjectSegmentationModel(
        name="segmenter",
        model_directory="segmenter",
        subscribed_camera=CAMERA,
    ).create_inference()

    assert isinstance(inference.model, adapter_class)
