import numpy as np
import pytest

from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_adapter import (
    Yolov5SegModelAdapter,
    Yolov8SegModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_schema import (
    ObjectSegmentationModelManifestSchema,
)


def make_manifest(
    model_format: str,
) -> ObjectSegmentationModelManifestSchema:
    return ObjectSegmentationModelManifestSchema.model_validate(
        {
            "schema_version": 1,
            "model_format": model_format,
            "weights": "model.onnx",
            "input": {"width": 10, "height": 10},
            "output": {
                "prediction_output_name": "predictions",
                "prototype_output_name": "prototypes",
                "class_names": ["part"],
                "mask_coefficient_count": 1,
            },
        }
    )


def test_yolov8_segmentation_skips_out_of_bounds_candidate() -> None:
    adapter = Yolov8SegModelAdapter(
        "segmenter",
        make_manifest("yolov8_seg"),
        max_detections=1,
    )
    prediction_rows = np.array(
        [
            [100.0, 100.0, 4.0, 4.0, 0.99, 1.0],
            [5.0, 5.0, 6.0, 6.0, 0.90, 1.0],
        ],
        dtype=np.float32,
    )
    predictions = prediction_rows.T[np.newaxis, ...]
    prototypes = np.ones((1, 1, 4, 4), dtype=np.float32)

    results = adapter.decode(predictions, prototypes, (10, 10))

    assert len(results) == 1
    assert results[0].bounding_box.model_dump() == pytest.approx(
        {"xmin": 0.2, "xmax": 0.8, "ymin": 0.2, "ymax": 0.8}
    )


def test_yolov5_segmentation_combines_object_and_class_confidence() -> None:
    adapter = Yolov5SegModelAdapter(
        "segmenter",
        make_manifest("yolov5_seg"),
    )
    predictions = np.array(
        [[[5.0, 5.0, 6.0, 6.0, 0.8, 0.5, 1.0]]],
        dtype=np.float32,
    )
    prototypes = np.ones((1, 1, 4, 4), dtype=np.float32)

    results = adapter.decode(predictions, prototypes, (10, 10))

    assert results[0].confidence == pytest.approx(0.4)


def test_segmentation_rejects_wrong_prototype_shape() -> None:
    adapter = Yolov8SegModelAdapter(
        "segmenter",
        make_manifest("yolov8_seg"),
    )
    predictions = np.ones((1, 6, 1), dtype=np.float32)
    prototypes = np.ones((1, 2, 4, 4), dtype=np.float32)

    with pytest.raises(ValueError, match="prototype shape"):
        adapter.decode(predictions, prototypes, (10, 10))
