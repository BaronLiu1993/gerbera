from datetime import datetime

import numpy as np
import pytest

from gerbera_sdk.inference import Frame
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_adapter import (
    DEFAULT_MAXIMUM_DEPTH_VALUES,
    DepthAnythingModelAdapter,
    MidasModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_schema import (
    ObjectDepthModelManifestSchema,
)


def make_manifest(
    model_format: str = "midas",
) -> ObjectDepthModelManifestSchema:
    return ObjectDepthModelManifestSchema.model_validate(
        {
            "schema_version": 1,
            "model_format": model_format,
            "weights": "model.onnx",
            "input": {"width": 256, "height": 256},
            "output": {
                "value_type": "relative_depth",
                "unit": "relative",
            },
        }
    )


@pytest.mark.parametrize(
    ("adapter_class", "model_format"),
    [
        (MidasModelAdapter, "midas"),
        (DepthAnythingModelAdapter, "depth_anything"),
    ],
)
def test_depth_adapters_extract_single_channel_maps(
    adapter_class,
    model_format: str,
) -> None:
    adapter = adapter_class("depth", make_manifest(model_format))
    prediction = np.ones((1, 1, 8, 12), dtype=np.float32)

    result = adapter.extract_depth_map(prediction)

    assert result.shape == (8, 12)


def test_depth_output_is_bounded_while_preserving_aspect_ratio() -> None:
    adapter = MidasModelAdapter("depth", make_manifest())
    prediction = np.ones((1, 1, 32, 32), dtype=np.float32)

    result = adapter.decode(prediction, (1080, 1920))

    assert result.size <= DEFAULT_MAXIMUM_DEPTH_VALUES
    assert result.shape[1] / result.shape[0] == pytest.approx(16 / 9, rel=0.01)


def test_depth_output_keeps_small_frame_resolution() -> None:
    adapter = MidasModelAdapter("depth", make_manifest())

    result = adapter.decode(
        np.ones((1, 1, 4, 4), dtype=np.float32),
        (60, 80),
    )

    assert result.shape == (60, 80)


def test_depth_output_rejects_non_finite_values() -> None:
    adapter = MidasModelAdapter("depth", make_manifest())
    prediction = np.full((1, 1, 4, 4), np.nan, dtype=np.float32)

    with pytest.raises(ValueError, match="NaN or infinite"):
        adapter.decode(prediction, (4, 4))


def test_estimate_returns_bounded_serializable_depth_map() -> None:
    class Network:
        def setInput(self, value: np.ndarray) -> None:
            self.input = value

        def forward(self) -> np.ndarray:
            return np.ones((1, 1, 16, 16), dtype=np.float32)

    adapter = MidasModelAdapter("depth", make_manifest())
    adapter.__dict__["model"] = Network()
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((1080, 1920, 3), dtype=np.uint8),
    )

    depth_map = adapter.estimate(frame)

    assert depth_map.width * depth_map.height <= DEFAULT_MAXIMUM_DEPTH_VALUES
    assert len(depth_map.values) == depth_map.height
