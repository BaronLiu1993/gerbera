from dataclasses import dataclass, field
import uuid

@dataclass(frozen=True)
class DeviceCameraSource:
    device_index: int = 0


@dataclass(frozen=True)
class MJPEGSource:
    stream_url: str


CameraSource = DeviceCameraSource | MJPEGSource


@dataclass
class Camera:
    name: str
    description: str
    source: CameraSource
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
