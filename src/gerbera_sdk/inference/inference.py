from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from gerbera_sdk.inference.cloud_model_adapter import (
    AnthropicCloudModelAdapter,
    GoogleCloudModelAdapter,
    OpenAICloudModelAdapter,
)

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.camera import Frame

Model: TypeAlias = (
    AnthropicCloudModelAdapter
    | OpenAICloudModelAdapter
    | GoogleCloudModelAdapter
)

VLM_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "VLM.md"
)


@dataclass
class VLMInference:
    model: Model
    user_prompt: str
    max_concurrent_model_inference: int = 1
    interval_seconds: float = 5.0

    @property
    def system_prompt(self) -> str:
        return VLM_SYSTEM_PROMPT_PATH.read_text().strip()

    def predict(self, frame: Frame) -> VLMFrameEnvironment:
        model_input = self.model.convert_to_valid_input(frame)
        output = self.model.predict(
            model_input=model_input,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            output_schema=VLMFrameEnvironment.model_json_schema(),
        )
        return VLMFrameEnvironment.model_validate(output)


class VLMFrameObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_name: str
    description: str
    x_coordinate: float = Field(ge=0.0, le=1.0)
    y_coordinate: float = Field(ge=0.0, le=1.0)


class VLMFrameEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_name: str
    description: str
    objects: list[VLMFrameObject]
