from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

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
from gerbera_sdk.utils import StrictSchema


VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)

VISION_LANGUAGE_MODEL_VALID_NAME = {
    VisionLanguageModelProviderEnum.ANTHROPIC: ["opus-4.6"],
    VisionLanguageModelProviderEnum.OPENAI: [],
    VisionLanguageModelProviderEnum.GOOGLE: []
}

@dataclass
class VisionLanguageModel(StrictSchema):
    # We need these
    name: str = Field(min_length=1)
    model_provider: VisionLanguageModelProviderEnum
    user_prompt: str = Field(min_length=1)
    model_name: str

    # We dont need these or unused for now
    description: str = ""
    interval_seconds: float = Field(default=5.0, gt=0) # Time between inferences

    def create(self) -> "VisionLanguageModelInference":
        if self.model_name not in VISION_LANGUAGE_MODEL_VALID_NAME[self.model_provider]:
            raise RuntimeError(f"Model Does Not Exist For Provider {self.model_provider}")

        model = VISION_LANGUAGE_MODEL_REGISTRY[self.model_provider]()

        return VisionLanguageModelInference(model=model, user_prompt=self.user_prompt)


@dataclass
class VisionLanguageModelInference:
    model: VisionLanguageModelAdapters
    user_prompt: str = Field(min_length=1)
    interval_seconds: float = 0.0 # Time between inferences

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
            self.model.convert_to_valid_input(frame.to_base64_string())
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
