from typing import TypeAlias

from gerbera_sdk.inference.frame import (
    BoundingBox,
    Frame,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    AnthropicVisionLanguageModelAdapter,
    GoogleVisionLanguageModelAdapter,
    OpenAIVisionLanguageModelAdapter,
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapter,
    VisionLanguageModelAdapters,
)
from gerbera_sdk.inference.model_types import (
    ObjectDetectionModelProviderEnum,
    VisionLanguageModelProviderEnum,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModel,
    VisionLanguageModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelFrameObject,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    OBJECT_DETECTION_MODEL_REGISTRY,
    ObjectDetectionAdapter,
    ObjectDetectionModelAdapters,
    Yolov5ModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModel,
    ObjectDetectionModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionObjectModel,
    PerceptionStateModel,
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
    "ObjectDetectionModelProviderEnum",
    "OBJECT_DETECTION_MODEL_REGISTRY",
    "ObjectDetectionAdapter",
    "ObjectDetectionModelAdapters",
    "ObjectDetectionModel",
    "ObjectDetectionModelInference",
    "PerceptionObjectModel",
    "PerceptionStateModel",
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
