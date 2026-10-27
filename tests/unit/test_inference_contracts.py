import pytest
from pydantic import ValidationError

from gerbera_sdk.inference import VisionLanguageModel, VisionLanguageModelProviderEnum
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource


@pytest.mark.parametrize("field, value", [
    ("timeout_seconds", -1.0), ("max_tokens", 0), ("interval_seconds", float("inf")),
    ("api_key", ""), ("model_name", " "),
])
def test_vision_configuration_rejects_unusable_settings(field, value) -> None:
    settings = dict(
        name="vision", model_provider=VisionLanguageModelProviderEnum.OPENAI,
        user_prompt="Observe", api_key="test", model_name="test-model",
        subscribed_camera=Camera(name="camera", description="Camera", source=DeviceCameraSource(0)),
    )
    settings[field] = value

    with pytest.raises(ValidationError, match=field):
        VisionLanguageModel(**settings)
