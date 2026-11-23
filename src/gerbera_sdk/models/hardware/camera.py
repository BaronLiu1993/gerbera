from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

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


@dataclass
class Frame:
    image: NDArray[np.uint8]
    timestamp: datetime
