from dataclasses import dataclass
from pathlib import Path

from gerbera_sdk.inference.frame import (
    Frame,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.inference import ModelTypes
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VisionLanguageModelAdapters,
)


VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)


@dataclass
class VisionLanguageModelInference:
    model: VisionLanguageModelAdapters
    name: str
    description: str
    user_prompt: str
    model_type: ModelTypes = ModelTypes.VISION_LANGUAGE_MODEL
    max_concurrent_model_inference: int = 1
    interval_seconds: float = 5.0

    @property
    def system_prompt(self) -> str:
        return VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH.read_text().strip()

    def predict(
        self,
        frames: list[Frame],
    ) -> VisionLanguageModelFrameEnvironment:
        if not frames:
            raise ValueError("At least one frame is required for inference")

        valid_frame_input = [
            self.model.convert_to_valid_input(frame)
            for frame in frames
        ]

        output = self.model.predict(
            model_input=valid_frame_input,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            output_schema=(
                VisionLanguageModelFrameEnvironment.model_json_schema()
            ),
        )
        return VisionLanguageModelFrameEnvironment.model_validate(output)

    def predict_with_base64(
        self,
        frames: list[str],
    ) -> VisionLanguageModelFrameEnvironment:
        if not frames:
            raise ValueError("At least one Base64 frame is required for inference")

        decoded_frames = [
            Frame.from_base64_string(frame)
            for frame in frames
        ]
        return self.predict(decoded_frames)
