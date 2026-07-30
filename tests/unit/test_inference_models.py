import base64
from datetime import datetime

import cv2
import numpy as np
import pytest

from gerbera_sdk.inference import (
    APIModel,
    APIModelAdapter,
    LocalModelAdapter,
    Model,
    ModelAdapter,
)
from gerbera_sdk.models.hardware.camera import Frame


class RecordingAPIAdapter(APIModelAdapter):
    def __init__(self) -> None:
        self.model_input = None

    def predict(self, model_input: object) -> object:
        self.model_input = model_input
        return {"accepted": True}


def test_base_model_and_adapters_are_abstract() -> None:
    with pytest.raises(TypeError):
        Model(name="model", description="test")

    with pytest.raises(TypeError):
        ModelAdapter()

    with pytest.raises(TypeError):
        APIModelAdapter()

    with pytest.raises(TypeError):
        LocalModelAdapter()


def test_api_model_converts_then_predicts() -> None:
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((4, 6, 3), dtype=np.uint8),
    )
    adapter = RecordingAPIAdapter()
    model = APIModel(
        name="api",
        description="test",
        adapter=adapter,
    )

    result = model.predict(frame)
    prefix = "data:image/jpeg;base64,"
    assert isinstance(adapter.model_input, str)
    assert adapter.model_input.startswith(prefix)
    decoded = cv2.imdecode(
        np.frombuffer(
            base64.b64decode(adapter.model_input.removeprefix(prefix)),
            dtype=np.uint8,
        ),
        cv2.IMREAD_COLOR,
    )

    assert result == {"accepted": True}
    assert decoded.shape == frame.image.shape


def test_api_model_raises_when_frame_encoding_fails(monkeypatch) -> None:
    monkeypatch.setattr(cv2, "imencode", lambda *args: (False, None))
    model = APIModel(
        name="api",
        description="test",
        adapter=RecordingAPIAdapter(),
    )
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((1, 1, 3), dtype=np.uint8),
    )

    with pytest.raises(RuntimeError, match="Could not encode camera frame"):
        model.predict(frame)
