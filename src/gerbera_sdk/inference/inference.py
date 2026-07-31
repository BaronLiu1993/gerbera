from typing import TypeAlias
from enum import Enum

from gerbera_sdk.inference.cloud_model_adapter import (
    AnthropicCloudModelAdapter,
    GoogleCloudModelAdapter,
    OpenAICloudModelAdapter,
)

ModelAdapters: TypeAlias = (
    AnthropicCloudModelAdapter
    | OpenAICloudModelAdapter
    | GoogleCloudModelAdapter
)

class ModelTypes(Enum):
    VISION_LANGUAGE_MODEL = "vision_language_model"
    NEURAL_NETWORK = "neural_network"

from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference,
)

Inference: TypeAlias = (
    VisionLanguageModelInference
)
