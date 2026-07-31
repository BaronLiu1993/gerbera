import json
from datetime import datetime

import cv2
import numpy as np
from pydantic import ValidationError
import pytest
import requests

from gerbera_sdk.inference import (
    CloudModelAdapter,
    Frame,
    OpenAICloudModelAdapter,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelBoundingBox,
)


class RecordingCloudModelAdapter(CloudModelAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="key", model="test-model")
        self.frames = []
        self.prediction_args = None

    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        self.frames.append(frame)
        return {"frame_index": len(self.frames) - 1}

    def predict(
        self,
        model_input: list[dict[str, object]],
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
    frames = [
        Frame(
            timestamp=datetime.now(),
            image=np.zeros((4, 6, 3), dtype=np.uint8),
        ),
        Frame(
            timestamp=datetime.now(),
            image=np.ones((4, 6, 3), dtype=np.uint8),
        ),
    ]
    adapter = RecordingCloudModelAdapter()
    inference = VisionLanguageModelInference(
        model=adapter,
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frame",
    )

    result = inference.predict(frames)

    assert adapter.frames == frames
    assert adapter.prediction_args == {
        "model_input": [{"frame_index": 0}, {"frame_index": 1}],
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


def test_vision_language_model_schema_is_strict_for_every_object() -> None:
    schema = VisionLanguageModelFrameEnvironment.model_json_schema()

    def assert_strict_objects(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
            for child in value.values():
                assert_strict_objects(child)
        elif isinstance(value, list):
            for child in value:
                assert_strict_objects(child)

    assert_strict_objects(schema)


def test_vision_language_model_requires_at_least_one_frame() -> None:
    inference = VisionLanguageModelInference(
        model=RecordingCloudModelAdapter(),
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frames",
    )

    with pytest.raises(ValueError, match="At least one frame"):
        inference.predict([])


@pytest.mark.parametrize(
    ("coordinates", "message"),
    [
        ({"x1": 0.5, "x2": 0.5, "y1": 0.1, "y2": 0.9}, "x1"),
        ({"x1": 0.1, "x2": 0.9, "y1": 0.5, "y2": 0.5}, "y1"),
    ],
)
def test_vision_language_model_rejects_zero_area_bounding_boxes(
    coordinates: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        VisionLanguageModelBoundingBox.model_validate(coordinates)


def test_vision_language_model_prompt_defines_normalized_coordinates() -> None:
    adapter = RecordingCloudModelAdapter()
    inference = VisionLanguageModelInference(
        model=adapter,
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frame",
    )

    assert "Gerbera hardware setup" in inference.system_prompt
    assert "one or more camera frames" in inference.system_prompt
    assert "frame_index" in inference.system_prompt
    assert "normalized coordinates" in inference.system_prompt
    assert "0.0 <= x1 < x2 <= 1.0" in inference.system_prompt
    assert "0.0 <= y1 < y2 <= 1.0" in inference.system_prompt


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


def test_openai_adapter_includes_response_body_in_http_errors(
    monkeypatch,
) -> None:
    request = requests.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    ).prepare()
    response = requests.Response()
    response.status_code = 400
    response.url = request.url
    response.request = request
    response._content = (
        b'{"error":{"message":"Invalid schema: '
        b'additionalProperties is required"}}'
    )
    monkeypatch.setattr(
        "gerbera_sdk.inference.cloud_model_adapter.requests.post",
        lambda *args, **kwargs: response,
    )
    adapter = OpenAICloudModelAdapter(
        api_key="key",
        model="gpt-5.6",
    )

    with pytest.raises(
        requests.HTTPError,
        match="OpenAI response.*additionalProperties is required",
    ):
        adapter.predict(
            model_input=[
                {
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,AA==",
                }
            ],
            system_prompt="Describe the image",
            user_prompt="What is visible?",
            output_schema=(
                VisionLanguageModelFrameEnvironment.model_json_schema()
            ),
        )


def test_openai_adapter_expands_multiple_images_into_content(
    monkeypatch,
) -> None:
    captured_request = {}
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "environment_name": "workshop",
                                    "description": "Two camera views",
                                    "objects": [],
                                }
                            ),
                        }
                    ]
                }
            ]
        }
    ).encode()

    def fake_post(url, **kwargs):
        captured_request.update(kwargs["json"])
        return response

    monkeypatch.setattr(
        "gerbera_sdk.inference.cloud_model_adapter.requests.post",
        fake_post,
    )
    adapter = OpenAICloudModelAdapter(
        api_key="key",
        model="gpt-5.6",
    )
    images = [
        {"type": "input_image", "image_url": "data:image/jpeg;base64,AA=="},
        {"type": "input_image", "image_url": "data:image/jpeg;base64,AQ=="},
    ]

    adapter.predict(
        model_input=images,
        system_prompt="Analyze every image",
        user_prompt="What changed?",
        output_schema=VisionLanguageModelFrameEnvironment.model_json_schema(),
    )

    assert captured_request["input"][0]["content"] == [
        {"type": "input_text", "text": "What changed?"},
        *images,
    ]
