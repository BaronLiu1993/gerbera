from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    ObjectDetectionAdapter,
)
from gerbera_sdk.utils import StrictSchema


class ObjectDetectionModel(StrictSchema):
    name: str = Field(min_length=1)
    model_type: Literal["object_detection"] = "object_detection"
    model_class: Literal["yolov5", "yolov8"] # Expand this to a config file later
    
    description: str


@dataclass
class ObjectDetectionModelInference:
    model: ObjectDetectionAdapter
    name: str
    description: str
    interval_seconds: float = 1.0
