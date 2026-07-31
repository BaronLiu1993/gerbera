from dataclasses import dataclass
from typing import TypeAlias, Field

from gerbera_sdk.inference.cloud_model_adapter import (
    AnthropicCloudModelAdapter,
    GoogleCloudModelAdapter,
    OpenAICloudModelAdapter,
)

Model: TypeAlias = (
    AnthropicCloudModelAdapter
    | OpenAICloudModelAdapter
    | GoogleCloudModelAdapter
)


@dataclass
class VLMInference:
    model: Model
    system_prompt: 
    user_prompt: str
    max_concurrent_model_inference: int = 1
    interval_seconds: float = 5.0

@dataclass
class VLMFrameObject:
    object_name: str
    description: str
    x_coordinate: float = Field(ge=0, le=1)
    y_coordinate: float = Field(ge=0, le=1)

@dataclass
class VLMFrameEnvironment:
    frame_name: str
    description: str
    objects: list[VLMFrameObject]

