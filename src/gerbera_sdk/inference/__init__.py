from __future__ import annotations

from typing_extensions import TypeAlias

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
)
from gerbera_sdk.inference.model_types import (
    ObjectDepthModelProviderEnum,
    ObjectDetectionModelProviderEnum,
    ObjectSegmentationModelProviderEnum,
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
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_adapter import (
    DepthAnythingModelAdapter,
    MidasModelAdapter,
    OBJECT_DEPTH_MODEL_REGISTRY,
    ObjectDepthAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_inference import (
    ObjectDepthModel,
    ObjectDepthModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_schema import (
    DepthMapModel,
    ObjectDepthStateModel,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_adapter import (
    OBJECT_SEGMENTATION_MODEL_REGISTRY,
    ObjectSegmentationAdapter,
    Yolov5SegModelAdapter,
    Yolov8SegModelAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_inference import (
    ObjectSegmentationModel,
    ObjectSegmentationModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_schema import (
    NormalizedPoint,
    ObjectSegmentationStateModel,
    SegmentationMaskModel,
    SegmentedObjectModel,
)


Inference: TypeAlias = (
    ObjectDepthModelInference
    | ObjectDetectionModelInference
    | ObjectSegmentationModelInference
    | VisionLanguageModelInference
)
Model: TypeAlias = (
    ObjectDepthModel
    | ObjectDetectionModel
    | ObjectSegmentationModel
    | VisionLanguageModel
)


__all__ = [
    "AnthropicVisionLanguageModelAdapter",
    "BoundingBox",
    "DepthAnythingModelAdapter",
    "DepthMapModel",
    "Frame",
    "GoogleVisionLanguageModelAdapter",
    "Inference",
    "Model",
    "MidasModelAdapter",
    "NormalizedPoint",
    "OBJECT_DEPTH_MODEL_REGISTRY",
    "VisionLanguageModelProviderEnum",
    "ObjectDepthAdapter",
    "ObjectDepthModel",
    "ObjectDepthModelInference",
    "ObjectDepthModelProviderEnum",
    "ObjectDepthStateModel",
    "ObjectDetectionModelProviderEnum",
    "OBJECT_DETECTION_MODEL_REGISTRY",
    "ObjectDetectionAdapter",
    "ObjectDetectionModel",
    "ObjectDetectionModelInference",
    "OBJECT_SEGMENTATION_MODEL_REGISTRY",
    "ObjectSegmentationAdapter",
    "ObjectSegmentationModel",
    "ObjectSegmentationModelInference",
    "ObjectSegmentationModelProviderEnum",
    "ObjectSegmentationStateModel",
    "PerceptionObjectModel",
    "PerceptionStateModel",
    "SegmentationMaskModel",
    "SegmentedObjectModel",
    "OpenAIVisionLanguageModelAdapter",
    "VisionLanguageModelAdapter",
    "VISION_LANGUAGE_MODEL_REGISTRY",
    "VisionLanguageModelFrameEnvironment",
    "VisionLanguageModelFrameObject",
    "VisionLanguageModel",
    "VisionLanguageModelInference",
    "Yolov5ModelAdapter",
    "Yolov5SegModelAdapter",
    "Yolov8SegModelAdapter",
]
