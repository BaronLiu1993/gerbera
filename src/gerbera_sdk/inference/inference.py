from enum import Enum
from typing import TypeAlias


class ModelTypes(Enum):
    VISION_LANGUAGE_MODEL = "vision_language_model"
    OBJECT_DETECTION = "object_detection"

from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModelInference
)

Inference: TypeAlias = (
    VisionLanguageModelInference,
    ObjectDetectionModelInference
)
