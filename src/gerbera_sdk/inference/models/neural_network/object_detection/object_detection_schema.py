from typing import Literal

from pydantic import Field, InstanceOf

from gerbera_sdk.inference.frame import BoundingBox, Frame
from gerbera_sdk.inference.model_types import ObjectDetectionModelProviderEnum
from gerbera_sdk.utils import StrictSchema


class ObjectDetectionModelInputSchema(StrictSchema):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ObjectDetectionModelOutputSchema(StrictSchema):
    prediction_count: int = Field(gt=0)
    class_names: list[str] = Field(min_length=1)


class ObjectDetectionModelManifestSchema(StrictSchema):
    input: ObjectDetectionModelInputSchema
    output: ObjectDetectionModelOutputSchema


class PerceptionObjectModel(StrictSchema):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox


class PerceptionStateModel(StrictSchema):
    camera_id: str = Field(min_length=1)
    frame: InstanceOf[Frame]
    model_name: str = Field(min_length=1)
    perception_objects: list[PerceptionObjectModel]
