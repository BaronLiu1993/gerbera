import json

import cv2
from pydantic import TypeAdapter, ValidationError
import pytest
import requests

from gerbera_sdk.inference import (
    BoundingBox,
    Model,
    ObjectDetectionModel,
    OpenAIVisionLanguageModelAdapter,
    VisionLanguageModelAdapter,
    VisionLanguageModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
    Yolov5ModelAdapter,
)
class RecordingVisionLanguageModelAdapter(VisionLanguageModelAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="key", model="test-model")
        self.frames = []
        self.prediction_args = None

    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
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


def test_yolov5_adapter_loads_weights_from_project_models(
    monkeypatch,
) -> None:
    loaded_paths = []
    model = object()
    monkeypatch.setattr(
        cv2.dnn,
        "readNetFromONNX",
        lambda path: loaded_paths.append(path) or model,
    )

    adapter = Yolov5ModelAdapter(weights_path="yolov5s.onnx")

    assert adapter.model is model
    assert adapter.model is model
    assert loaded_paths == [".gerbera/models/yolov5s.onnx"]


@pytest.mark.parametrize(
    ("definition", "model_class"),
    [
        (
            {
                "name": "detector",
                "model_type": "object_detection",
                "model_class": "yolov5",
                "weights": "detector.onnx",
                "class_names": ["part"],
                "description": "Detect parts",
            },
            ObjectDetectionModel,
        ),
        (
            {
                "name": "observer",
                "model_type": "vision_language_model",
                "model_class": "openai",
                "model_name": "vision-model",
                "description": "Observe the workspace",
                "user_prompt": "Describe the workspace",
            },
            VisionLanguageModel,
        ),
    ],
)
def test_model_type_selects_model_schema(
    definition: dict[str, object],
    model_class: type[ObjectDetectionModel] | type[VisionLanguageModel],
) -> None:
    model = TypeAdapter(Model).validate_python(definition)

    assert isinstance(model, model_class)


def test_vision_language_model_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        VisionLanguageModelAdapter(api_key="key", model="test-model")


def test_vision_language_model_converts_then_predicts() -> None:
    frames = ["first-base64-frame", "second-base64-frame"]
    adapter = RecordingVisionLanguageModelAdapter()
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
        model=RecordingVisionLanguageModelAdapter(),
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frames",
    )

    with pytest.raises(ValueError, match="At least one frame"):
        inference.predict([])


def test_vision_language_model_predicts_with_base64_strings() -> None:
    adapter = RecordingVisionLanguageModelAdapter()
    inference = VisionLanguageModelInference(
        model=adapter,
        name="vision",
        description="Test vision model",
        user_prompt="Describe the frames",
    )

    frames = ["first-base64-frame", "second-base64-frame"]
    result = inference.predict(frames)

    assert adapter.prediction_args["model_input"] == [
        {"frame_index": 0},
        {"frame_index": 1},
    ]
    assert adapter.frames == frames
    assert result.environment_name == "workshop"


@pytest.mark.parametrize(
    ("coordinates", "message"),
    [
        (
            {"xmin": 0.5, "xmax": 0.5, "ymin": 0.1, "ymax": 0.9},
            "xmin",
        ),
        (
            {"xmin": 0.1, "xmax": 0.9, "ymin": 0.5, "ymax": 0.5},
            "ymin",
        ),
    ],
)
def test_vision_language_model_rejects_zero_area_bounding_boxes(
    coordinates: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        BoundingBox.model_validate(coordinates)


def test_vision_language_model_prompt_defines_normalized_coordinates() -> None:
    adapter = RecordingVisionLanguageModelAdapter()
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
    assert "0.0 <= xmin < xmax <= 1.0" in inference.system_prompt
    assert "0.0 <= ymin < ymax <= 1.0" in inference.system_prompt


def test_openai_adapter_formats_base64_input(
) -> None:
    adapter = OpenAIVisionLanguageModelAdapter(
        api_key="key",
        model="test-model",
    )

    assert adapter.convert_to_valid_input("AA==") == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,AA==",
    }


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
        "gerbera_sdk.inference.models.vision_language_model."
        "vision_language_model_adapter.requests.post",
        lambda *args, **kwargs: response,
    )
    adapter = OpenAIVisionLanguageModelAdapter(
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
        "gerbera_sdk.inference.models.vision_language_model."
        "vision_language_model_adapter.requests.post",
        fake_post,
    )
    adapter = OpenAIVisionLanguageModelAdapter(
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
