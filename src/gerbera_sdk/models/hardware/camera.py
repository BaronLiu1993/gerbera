from dataclasses import dataclass, field
import uuid
import numpy as np
from numpy.typing import NDArray
from datetime import datetime

@dataclass(frozen=True)
class DeviceCameraSource:
    device_index: int

@dataclass(frozen=True)
class MJPEGSource:
    stream_url: str

@dataclass(frozen=True)
class APIModel:
    name: str
    description: str
    model_url: str

@dataclass(frozen=True)
class LocalModel:
    name: str
    description: str

CameraSource = DeviceCameraSource | MJPEGSource
Model = APIModel | LocalModel
    

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
    subscribed_models: list[Model] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
