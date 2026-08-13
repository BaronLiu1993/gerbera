from enum import Enum
from typing import Literal

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference,
)
from gerbera_sdk.utils import StrictSchema


class VisionLanguageModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"

class ObjectDetectionModelProviderEnum(Enum):
    YOLOV5 = "yolov5"
    YOLOV8 = "yolov8"


ModelCatalogType = Literal["object_detection", "vision_language_model"]
MODEL_CATALOG_TYPE_REGISTRY: dict[type, ModelCatalogType] = {
    ObjectDetectionModelInference: "object_detection",
    VisionLanguageModelInference: "vision_language_model",
}


class SubscribedCameraCatalogEntry(StrictSchema):
    camera_id: str
    name: str


class ModelCatalogEntry(StrictSchema):
    model_id: str
    name: str
    description: str
    model_type: ModelCatalogType
    subscribed_cameras: list[SubscribedCameraCatalogEntry]
    is_running: bool
    turn_on_tool: str
    turn_off_tool: str
    read_tool: str
    single_inference_tool: str
