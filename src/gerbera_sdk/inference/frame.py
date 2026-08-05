import base64
import binascii
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np
from numpy.typing import NDArray
from pydantic import Field, model_validator

from gerbera_sdk.utils import StrictSchema


class BoundingBox(StrictSchema):
    xmin: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized left edge; must be less than xmax.",
    )
    xmax: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized right edge; must be greater than xmin.",
    )
    ymin: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized top edge; must be less than ymax.",
    )
    ymax: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized bottom edge; must be greater than ymin.",
    )

    @model_validator(mode="after")
    def validate_edge_order(self) -> "BoundingBox":
        if self.xmin >= self.xmax:
            raise ValueError("xmin must be less than xmax")
        if self.ymin >= self.ymax:
            raise ValueError("ymin must be less than ymax")
        return self


@dataclass
class Frame:
    timestamp: datetime
    image: NDArray[np.uint8]

    def to_base64_string(self) -> str:
        success, encoded_image = cv2.imencode(".jpg", self.image)
        if not success:
            raise RuntimeError("Could not encode camera frame")

        return base64.b64encode(encoded_image.tobytes()).decode("ascii")
