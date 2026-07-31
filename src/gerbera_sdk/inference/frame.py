from dataclasses import dataclass
from datetime import datetime

import numpy as np
from numpy.typing import NDArray


@dataclass
class Frame:
    timestamp: datetime
    image: NDArray[np.uint8]
