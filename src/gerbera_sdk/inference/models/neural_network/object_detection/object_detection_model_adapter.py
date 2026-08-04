from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property

import cv2
import numpy as np
from numpy.typing import NDArray

from gerbera_sdk.paths import MODELS_PATH


@dataclass
class ObjectDetectionAdapter(ABC):
    weights_path: str

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(
            str(MODELS_PATH / self.weights_path)
        )
    @abstractmethod
    def validate_output(self):
        pass

    @abstractmethod
    def detect(self):
        pass

    @abstractmethod
    def decode(self):
        pass

    

class Yolov5ModelAdapter(ObjectDetectionAdapter):
    def validate_output(self):
        pass
    
    def decode(self):
        pass

    def detect(self, frame: NDArray[np.uint8]):
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1 / 255.0,
            size=(640, 640),
            swapRB=True,
            crop=False,
        )
        self.model.setInput(blob)
        predictions = self.model.forward()
        print(predictions)
