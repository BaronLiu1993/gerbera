from dataclasses import field
from typing import Annotated
import uuid

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

# Camera Sources
@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class DeviceCameraSource:
    device_index: Annotated[int, Field(ge=0)]


@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class MJPEGSource:
    stream_url: Annotated[str, Field(min_length=1, pattern=r"\S")]


CameraSource = DeviceCameraSource | MJPEGSource


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Camera:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    description: str
    source: CameraSource
    camera_id: Annotated[str, Field(min_length=1, pattern=r"\S")] = field(default_factory=lambda: str(uuid.uuid4()))
