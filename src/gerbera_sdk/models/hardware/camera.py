from dataclasses import dataclass, field
import uuid
import numpy as np
from numpy.typing import NDArray
from datetime import datetime

from gerbera_sdk.inference.inference import Inference

# Camera Sources
@dataclass(frozen=True)
class DeviceCameraSource:
    device_index: int

@dataclass(frozen=True)
class MJPEGSource:
    stream_url: str

CameraSource = DeviceCameraSource | MJPEGSource

@dataclass
class Frame:
    timestamp: datetime
    image: NDArray[np.uint8]

@dataclass
class Camera:
    name: str
    description: str
    source: CameraSource
    latest_frame: Frame | None = None
    subscribed_models: list[Inference] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
