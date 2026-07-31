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
