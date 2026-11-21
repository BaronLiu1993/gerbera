from dataclasses import dataclass
from datetime import datetime

import numpy as np
from numpy.typing import NDArray

@dataclass
class Camera:
    camera_id: str
    camera_source: int | str


@dataclass
class Frame:
    image: NDArray[np.uint8]
    timestamp: datetime
