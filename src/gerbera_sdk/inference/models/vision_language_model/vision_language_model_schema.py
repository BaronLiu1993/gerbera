from pydantic import Field

from gerbera_sdk.inference.frame import BoundingBox
from gerbera_sdk.utils import StrictSchema


class VisionLanguageModelFrameObject(StrictSchema):
    frame_index: int = Field(
        ge=0,
        description="Zero-based index of the image containing this object.",
    )
    object_name: str
    description: str
    bounding_box: BoundingBox
    center_x_coordinate: float = Field(ge=0.0, le=1.0)
    center_y_coordinate: float = Field(ge=0.0, le=1.0)


class VisionLanguageModelFrameEnvironment(StrictSchema):
    environment_name: str
    description: str
    objects: list[VisionLanguageModelFrameObject]
