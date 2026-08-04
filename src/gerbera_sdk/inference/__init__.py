from typing import TypeAlias

from gerbera_sdk.inference.frame import (
    BoundingBox,
    Frame,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelFrameObject,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    AnthropicVisionLanguageModelAdapter,
    GoogleVisionLanguageModelAdapter,
    OpenAIVisionLanguageModelAdapter,
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapter,
    VisionLanguageModelAdapters,
)
from gerbera_sdk.inference.model_types import VisionLanguageModelProviderEnum
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModel,
    VisionLanguageModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    ObjectDetectionAdapter,
    Yolov5ModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModel,
    ObjectDetectionModelInference,
)


Inference: TypeAlias = (
    ObjectDetectionModelInference | VisionLanguageModelInference
)
Model: TypeAlias = ObjectDetectionModel | VisionLanguageModel

__all__ = [
    "AnthropicVisionLanguageModelAdapter",
    "BoundingBox",
    "Frame",
    "GoogleVisionLanguageModelAdapter",
    "Inference",
    "Model",
    "VisionLanguageModelProviderEnum",
    "ObjectDetectionAdapter",
    "ObjectDetectionModel",
    "ObjectDetectionModelInference",
    "OpenAIVisionLanguageModelAdapter",
    "VisionLanguageModelAdapter",
    "VISION_LANGUAGE_MODEL_REGISTRY",
    "VisionLanguageModelAdapters",
    "VisionLanguageModelFrameEnvironment",
    "VisionLanguageModelFrameObject",
    "VisionLanguageModel",
    "VisionLanguageModelInference",
    "Yolov5ModelAdapter",
]
