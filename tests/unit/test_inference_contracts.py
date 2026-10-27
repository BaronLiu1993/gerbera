import pytest
from pydantic import ValidationError

from gerbera_sdk.inference import VisionLanguageModel, VisionLanguageModelProviderEnum
from gerbera_sdk.inference import DepthMapModel
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


def test_depth_extrema_are_derived_from_immutable_samples() -> None:
    depth = DepthMapModel(
        width=2, height=1, values=((3.0, 5.0),), value_type="relative_depth", unit="relative",
    )

    assert (depth.minimum_value, depth.maximum_value) == (3.0, 5.0)
    with pytest.raises(ValidationError):
        depth.values = ((100.0, 200.0),)


def test_depth_rejects_independently_supplied_extrema() -> None:
    with pytest.raises(ValidationError, match="minimum_value"):
        DepthMapModel(
            width=1, height=1, values=((3.0,),), value_type="relative_depth", unit="relative",
            minimum_value=100.0,
        )
