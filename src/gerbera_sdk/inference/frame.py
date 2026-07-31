import base64
import binascii
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass
class Frame:
    timestamp: datetime
    image: NDArray[np.uint8]

    @classmethod
    def from_base64_string(cls, base64_string: str) -> "Frame":
        image_data = base64_string
        if base64_string.startswith("data:"):
            header, separator, image_data = base64_string.partition(",")
            if not separator or ";base64" not in header:
                raise ValueError("Image must be a Base64 data URL")

        try:
            image_bytes = base64.b64decode(image_data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Image contains invalid Base64 data") from exc

        image = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            raise ValueError("Base64 data is not a supported image")

        return cls(timestamp=datetime.now(), image=image)
