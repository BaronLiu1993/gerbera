from enum import Enum
from typing import Literal

from gerbera_sdk.utils import StrictSchema, build_hashable_key


class VisionLanguageModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class ObjectDetectionModelProviderEnum(Enum):
    YOLOV5 = "yolov5"
    YOLOV8 = "yolov8"


ModelCatalogType = Literal["object_detection", "vision_language_model"]


def build_model_output_keys(
    model_id: str,
    camera_id: str,
    operations: tuple[str, ...],
) -> dict[str, dict[str, str]]:
    return {
        operation: {
            camera_id: build_hashable_key(model_id, camera_id, operation),
        }
        for operation in operations
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
    scene_objects_read_tool: str | None = None
    scene_objects_tool: str | None = None
    scene_analysis_read_tool: str | None = None
    scene_analysis_tool: str | None = None
