from typing import Annotated, Literal

from pydantic import Field, InstanceOf

from gerbera_sdk.inference.frame import BoundingBox, Frame
from gerbera_sdk.inference.model_types import (
    ObjectSegmentationModelProviderEnum,
)
from gerbera_sdk.utils import StrictSchema


class ObjectSegmentationModelInputSchema(StrictSchema):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    scale_factor: float = Field(default=1 / 255.0, gt=0)
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    swap_red_blue: bool = True


class ObjectSegmentationModelOutputSchema(StrictSchema):
    prediction_output_name: str = Field(min_length=1)
    prototype_output_name: str = Field(min_length=1)
    class_names: list[Annotated[str, Field(min_length=1)]] = Field(
        min_length=1
    )
    mask_coefficient_count: int = Field(gt=0)


class ObjectSegmentationModelManifestSchema(StrictSchema):
    schema_version: Literal[1]
    model_format: ObjectSegmentationModelProviderEnum
    weights: str = Field(min_length=1)
    input: ObjectSegmentationModelInputSchema
    output: ObjectSegmentationModelOutputSchema


class NormalizedPoint(StrictSchema):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class SegmentationMaskModel(StrictSchema):
    polygons: list[
        Annotated[list[NormalizedPoint], Field(min_length=3)]
    ]


class SegmentedObjectModel(StrictSchema):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    mask: SegmentationMaskModel


class ObjectSegmentationStateModel(StrictSchema):
    camera_id: str = Field(min_length=1)
    frame: InstanceOf[Frame]
    model_name: str = Field(min_length=1)
    segmented_objects: list[SegmentedObjectModel]
