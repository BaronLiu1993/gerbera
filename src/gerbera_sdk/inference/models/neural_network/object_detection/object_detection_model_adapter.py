from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import TypeAlias

import cv2

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.model_types import ObjectDetectionModelProviderEnum
from gerbera_sdk.paths import MODELS_PATH


@dataclass
class ObjectDetectionAdapter(ABC):
    model_source: str

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(
            str(MODELS_PATH / self.model_source)
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

    def detect(self, frame: list[Frame]):
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


class Yolov8ModelAdapter(ObjectDetectionAdapter):
    def validate_output(self):
        pass
    
    def decode(self):
        pass

    def detect(self, frame: list[Frame]):
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

ObjectDetectionModelAdapters: TypeAlias = Yolov5ModelAdapter 

OBJECT_DETECTION_MODEL_REGISTRY = {
    ObjectDetectionModelProviderEnum.YOLOV5: Yolov5ModelAdapter,
}
