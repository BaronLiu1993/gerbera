from datetime import datetime

import cv2
import numpy as np
import pytest

from gerbera_sdk.inference import (
    CloudModelAdapter,
    Frame,
    OpenAICloudModelAdapter,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)


class RecordingCloudModelAdapter(CloudModelAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="key", model="test-model")
        self.frame = None
        self.prediction_args = None

    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        self.frame = frame
        return {"converted": True}

    def predict(
        self,
        model_input: object,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        self.prediction_args = {
            "model_input": model_input,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_schema": output_schema,
        }
        return {
            "environment_name": "workshop",
            "description": "A workbench",
            "objects": [],
        }


def test_cloud_model_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        CloudModelAdapter(api_key="key", model="test-model")


def test_vision_language_model_converts_then_predicts() -> None:
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((4, 6, 3), dtype=np.uint8),
    )
    adapter = RecordingCloudModelAdapter()
    inference = VisionLanguageModelInference(
        model=adapter,
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frame",
    )

    result = inference.predict(frame)

    assert adapter.frame is frame
    assert adapter.prediction_args == {
        "model_input": {"converted": True},
        "system_prompt": inference.system_prompt,
        "user_prompt": "Describe the frame",
        "output_schema": (
            VisionLanguageModelFrameEnvironment.model_json_schema()
        ),
    }
    assert result == VisionLanguageModelFrameEnvironment(
        environment_name="workshop",
        description="A workbench",
        objects=[],
    )


def test_cloud_model_adapter_raises_when_frame_encoding_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(cv2, "imencode", lambda *args: (False, None))
    adapter = OpenAICloudModelAdapter(
        api_key="key",
        model="test-model",
    )
    frame = Frame(
        timestamp=datetime.now(),
        image=np.zeros((1, 1, 3), dtype=np.uint8),
    )

    with pytest.raises(RuntimeError, match="Could not encode camera frame"):
        adapter.convert_to_valid_input(frame)
