from dataclasses import field
from dataclasses import dataclass

from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.models.hardware.microcontroller import Microcontroller

@dataclass
class HardwareSystem:
    # microcontrollers used
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    # models and camera inputs
    cameras: list[Camera] = field(default_factory=list)
