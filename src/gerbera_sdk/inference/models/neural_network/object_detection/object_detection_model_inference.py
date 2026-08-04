from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    ObjectDetectionAdapter,
)
from gerbera_sdk.inference.model_types import (
    ObjectDetectionModelProviderEnum,
)

@dataclass
class ObjectDetectionModel:
    model_type: ObjectDetectionModelProviderEnum
    name: str = Field(min_length=1)
    model_source: str = Field(min_length=1)
    description: str = ""


@dataclass
class ObjectDetectionModelInference:
    model: ObjectDetectionAdapter
    name: str
    description: str
    interval_seconds: float = 1.0

    