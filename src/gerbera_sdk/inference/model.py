from typing import TypeAlias

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModel,
)


Model: TypeAlias = ObjectDetectionModel | VisionLanguageModel
