from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.inference import ModelAdapters, ModelTypes


VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)


class VisionLanguageModelBoundingBox(BaseModel):
    """Normalized box with ordered horizontal and vertical boundaries."""

    model_config = ConfigDict(extra="forbid")
    x1: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized left edge; must be less than x2.",
    )
    x2: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized right edge; must be greater than x1.",
    )
    y1: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized top edge; must be less than y2.",
    )
    y2: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized bottom edge; must be greater than y1.",
    )

    @model_validator(mode="after")
    def validate_edge_order(self) -> "VisionLanguageModelBoundingBox":
        if self.x1 >= self.x2:
            raise ValueError("x1 must be less than x2")
        if self.y1 >= self.y2:
            raise ValueError("y1 must be less than y2")
        return self


class VisionLanguageModelFrameObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_index: int = Field(
        ge=0,
        description="Zero-based index of the image containing this object.",
    )
    object_name: str
    description: str
    bounding_box: VisionLanguageModelBoundingBox
    center_x_coordinate: float = Field(ge=0.0, le=1.0)
    center_y_coordinate: float = Field(ge=0.0, le=1.0)


class VisionLanguageModelFrameEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_name: str
    description: str
    objects: list[VisionLanguageModelFrameObject]


@dataclass
class VisionLanguageModelInference:
    model: ModelAdapters
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
