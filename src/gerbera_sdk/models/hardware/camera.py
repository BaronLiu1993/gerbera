from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal, TypeAlias

import cv2
import numpy as np
from numpy.typing import NDArray

CameraOutputFormat: TypeAlias = Literal[".jpg", ".png"]

@dataclass
class DeviceCameraSource:
    source: int

    @property
    def capture_address(self) -> int:
        return self.source

@dataclass
class MJPEGSource:
    source: str

    @property
    def capture_address(self) -> str:
        return self.source

CameraSource: TypeAlias = DeviceCameraSource | MJPEGSource

@dataclass
class Camera:
    camera_id: str
    camera_source: CameraSource
    output_height: int = 360
    output_width: int = 640
    output_format: CameraOutputFormat = ".jpg"


@dataclass
class Frame:
    image: NDArray[np.uint8]
    timestamp: datetime
    output_format: CameraOutputFormat = ".jpg"

    def normalise_frame(
        self,
        output_height: int,
        output_width: int,
        output_format: CameraOutputFormat,
    ) -> "Frame":
        image_height, image_width = self.image.shape[:2]
        scale = min(output_width / image_width, output_height / image_height)
        resized_width = round(image_width * scale)
        resized_height = round(image_height * scale)

        if scale < 1:
            interpolation = cv2.INTER_AREA
        else:
            interpolation = cv2.INTER_LINEAR

        resized_image = cv2.resize(
            self.image, (resized_width, resized_height), interpolation=interpolation
        )

        vertical_padding = output_height - resized_height
        horizontal_padding = output_width - resized_width
        top = vertical_padding // 2
        left = horizontal_padding // 2
        framed_image = cv2.copyMakeBorder(
            resized_image,
            top,
            vertical_padding - top,
            left,
            horizontal_padding - left,
            cv2.BORDER_CONSTANT,
            value=0,
        )
        return replace(self, image=framed_image, output_format=output_format)

    def encode(self) -> bytes:
        _, encoded_image = cv2.imencode(self.output_format, self.image)
        return encoded_image.tobytes()
