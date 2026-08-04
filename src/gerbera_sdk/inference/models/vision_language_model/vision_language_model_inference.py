from dataclasses import dataclass
from pathlib import Path

from pydantic import Field
import threading

from gerbera_sdk.inference.frame import (
    Frame,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapters,
)
from gerbera_sdk.inference.model_types import (
    VisionLanguageModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera

VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)

VISION_LANGUAGE_MODEL_VALID_NAME = {
    VisionLanguageModelProviderEnum.ANTHROPIC: ["opus-4.6"],
    VisionLanguageModelProviderEnum.OPENAI: [],
    VisionLanguageModelProviderEnum.GOOGLE: [],
}


class VisionLanguageModel:
    # We need these
    name: str = Field(min_length=1)
    model_provider: VisionLanguageModelProviderEnum

    # Pass To the Model Itself
    user_prompt: str = Field(min_length=1)
    api_key: str
    model_name: str
    timeout_seconds: float = 120.0
    max_tokens: int = 1024

    subscribed_cameras: list[Camera] = Field(default_factory=list)

    # optional
    description: str = ""
    interval_seconds: float = Field(default=5.0, gt=0)

    @property
    def model(self) -> "VisionLanguageModelInference":
        if self.model_name not in VISION_LANGUAGE_MODEL_VALID_NAME[self.model_provider]:
            raise RuntimeError(
                f"Model Does Not Exist For Provider {self.model_provider}"
            )

        vision_language_model_object = VISION_LANGUAGE_MODEL_REGISTRY[
            self.model_provider
        ](
            api_key=self.api_key,
            model=self.model_name,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )

        return VisionLanguageModelInference(
            model=vision_language_model_object,
            user_prompt=self.user_prompt,
        )


@dataclass
class VLMSession:
    model: VisionLanguageModel
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None


@dataclass
class VisionLanguageModelInference:
    model_session: VLMSession
    user_prompt: str = Field(min_length=1)
    interval_seconds: float = 0.0

    @property
    def system_prompt(self) -> str:
        return VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH.read_text().strip()

    def turn_on_prediction_loop(self):
        pass

    def turn_off_prediction_loop(self):
        pass

    def prediction_loop(self):
        pass

    def predict(
        self,
        frames: list[Frame],
    ) -> VisionLanguageModelFrameEnvironment:
        if not frames:
            raise ValueError("At least one frame is required for inference")

        valid_frame_input = [
            self.model.convert_to_valid_input(frame.to_base64_string())
            for frame in frames
        ]

        output = self.model.predict(
            model_input=valid_frame_input,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            output_schema=(VisionLanguageModelFrameEnvironment.model_json_schema()),
        )
        return VisionLanguageModelFrameEnvironment.model_validate(output)
