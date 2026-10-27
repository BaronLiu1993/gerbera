import math
from typing import Literal

from pydantic import ConfigDict, Field, InstanceOf, computed_field, model_validator

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.model_types import ObjectDepthModelProviderEnum
from gerbera_sdk.utils import StrictSchema


class ObjectDepthModelInputSchema(StrictSchema):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    scale_factor: float = Field(default=1 / 255.0, gt=0)
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    standard_deviation: tuple[float, float, float] = (1.0, 1.0, 1.0)
    swap_red_blue: bool = True

    @model_validator(mode="after")
    def validate_standard_deviation(self) -> "ObjectDepthModelInputSchema":
        if any(value <= 0 for value in self.standard_deviation):
            raise ValueError("Depth input standard deviations must be positive")
        return self


class ObjectDepthModelOutputSchema(StrictSchema):
    value_type: Literal["relative_depth", "inverse_depth", "metric_depth"]
    unit: Literal["relative", "meters"]

    @model_validator(mode="after")
    def validate_unit(self) -> "ObjectDepthModelOutputSchema":
        if self.value_type == "metric_depth" and self.unit != "meters":
            raise ValueError("Metric depth output must use meters")
        if self.value_type != "metric_depth" and self.unit != "relative":
            raise ValueError("Relative depth output must use relative units")
        return self


class ObjectDepthModelManifestSchema(StrictSchema):
    schema_version: Literal[1]
    model_format: ObjectDepthModelProviderEnum
    weights: str = Field(min_length=1)
    input: ObjectDepthModelInputSchema
    output: ObjectDepthModelOutputSchema


class DepthMapModel(StrictSchema):
    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    values: tuple[tuple[float, ...], ...]
    value_type: Literal["relative_depth", "inverse_depth", "metric_depth"]
    unit: Literal["relative", "meters"]

    @model_validator(mode="after")
    def validate_values(self) -> "DepthMapModel":
        if len(self.values) != self.height:
            raise ValueError("Depth map row count must match its height")
        if any(len(row) != self.width for row in self.values):
            raise ValueError("Depth map column count must match its width")
        if not all(math.isfinite(value) for row in self.values for value in row):
            raise ValueError("Depth map contains NaN or infinite values")
        if self.value_type == "metric_depth" and self.unit != "meters":
            raise ValueError("Metric depth maps must use meters")
        if self.value_type != "metric_depth" and self.unit != "relative":
            raise ValueError("Relative depth maps must use relative units")
        return self

    @computed_field
    @property
    def minimum_value(self) -> float:
        return min(value for row in self.values for value in row)

    @computed_field
    @property
    def maximum_value(self) -> float:
        return max(value for row in self.values for value in row)


class ObjectDepthStateModel(StrictSchema):
    camera_id: str = Field(min_length=1)
    frame: InstanceOf[Frame]
    model_name: str = Field(min_length=1)
    depth_map: DepthMapModel
