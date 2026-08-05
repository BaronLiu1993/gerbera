from datetime import datetime

import numpy as np
import pytest
import yaml

from gerbera_sdk.inference import Frame, Yolov5ModelAdapter


def make_predictions() -> np.ndarray:
    return np.zeros((1, 25200, 85), dtype=np.float32)


@pytest.fixture
def adapter(tmp_path, monkeypatch) -> Yolov5ModelAdapter:
    class_names = [f"class_{index}" for index in range(80)]
    class_names[0] = "person"
    class_names[56] = "chair"

    manifest = {
        "schema_version": 1,
        "model_format": "yolov5",
        "input": {"width": 640, "height": 640},
        "output": {
            "prediction_count": 25200,
            "class_names": class_names,
        },
    }
    manifest_path = tmp_path / "yolov5n.onnx.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest))
    monkeypatch.setattr(
        "gerbera_sdk.inference.models.neural_network.object_detection."
        "object_detection_model_adapter.MODELS_PATH",
        tmp_path,
    )

    return Yolov5ModelAdapter(model_source="yolov5n.onnx")


def test_manifest_is_loaded_from_model_source_yaml(
    adapter: Yolov5ModelAdapter,
) -> None:
    assert adapter.manifest.input.width == 640
    assert adapter.manifest.input.height == 640
    assert adapter.manifest.output.prediction_count == 25200
    assert adapter.manifest.output.class_names[56] == "chair"


def test_validate_output_accepts_standard_yolov5_output(
    adapter: Yolov5ModelAdapter,
) -> None:

    adapter.validate_output(make_predictions())


def test_validate_output_rejects_wrong_shape(
    adapter: Yolov5ModelAdapter,
) -> None:
    predictions = np.zeros((1, 8400, 85), dtype=np.float32)

    with pytest.raises(ValueError, match=r"expected \(1, 25200, 85\)"):
        adapter.validate_output(predictions)


def test_validate_output_rejects_non_finite_values(
    adapter: Yolov5ModelAdapter,
) -> None:
    predictions = make_predictions()
    predictions[0, 0, 0] = np.nan

    with pytest.raises(ValueError, match="NaN or infinite"):
        adapter.validate_output(predictions)


def test_decode_combines_scores_and_applies_class_aware_nms(
    adapter: Yolov5ModelAdapter,
) -> None:
    predictions = make_predictions()

    # Two overlapping chair predictions. NMS should retain the stronger one.
    predictions[0, 0, :5] = [320, 320, 200, 200, 0.90]
    predictions[0, 0, 5 + 56] = 0.90
    predictions[0, 1, :5] = [325, 325, 200, 200, 0.80]
    predictions[0, 1, 5 + 56] = 0.80

    # A person at the same location must survive class-aware NMS.
    predictions[0, 2, :5] = [320, 320, 200, 200, 0.95]
    predictions[0, 2, 5] = 0.90

    detections = adapter.decode(predictions)

    assert [detection.class_name for detection in detections] == [
        "person",
        "chair",
    ]
    assert detections[0].confidence == pytest.approx(0.855)
    assert detections[1].confidence == pytest.approx(0.81)
    assert detections[1].bounding_box.model_dump() == pytest.approx(
        {
            "xmin": 220 / 640,
            "xmax": 420 / 640,
            "ymin": 220 / 640,
            "ymax": 420 / 640,
        }
    )


def test_detect_returns_decoded_objects(
    adapter: Yolov5ModelAdapter,
) -> None:
    class FakeNetwork:
        def __init__(self, predictions: np.ndarray) -> None:
            self.predictions = predictions
            self.input = None

        def setInput(self, value: np.ndarray) -> None:
            self.input = value

        def forward(self) -> np.ndarray:
            return self.predictions

    predictions = make_predictions()
    predictions[0, 0, :5] = [320, 320, 200, 200, 0.90]
    predictions[0, 0, 5 + 56] = 0.90
    network = FakeNetwork(predictions)

    adapter.__dict__["model"] = network
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((480, 640, 3), dtype=np.uint8),
    )

    detections = adapter.detect(frame)

    assert network.input.shape == (1, 3, 640, 640)
    assert len(detections) == 1
    assert detections[0].class_name == "chair"
