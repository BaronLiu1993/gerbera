from dataclasses import dataclass, field

from pydantic import Field
import threading

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    OBJECT_DETECTION_MODEL_REGISTRY,
    ObjectDetectionModelAdapters,
)
from gerbera_sdk.inference.model_types import (
    ObjectDetectionModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera


@dataclass
class ObjectDetectionModel:
    name: str = Field(min_length=1)
    model_name: ObjectDetectionModelProviderEnum # Yolov5 or whatever
    model_source: str = Field(min_length=1)
    subscribed_cameras: list[Camera] = field(default_factory=list)
    description: str = ""

    @property
    def model(self) -> "ObjectDetectionModelInference":
        if self.model_name not in OBJECT_DETECTION_MODEL_REGISTRY[self.model_name]:
            raise RuntimeError(
                f"Model Does Not Exist For Provider {self.model_name}"
            )
        adapter = OBJECT_DETECTION_MODEL_REGISTRY[self.model_name]
        object_detection_model = adapter(model_source=self.model_source)

        return ObjectDetectionModelInference(
            model=object_detection_model,
            name=self.name,
            description=self.description,
        )


@dataclass
class VLMSession:
    model: ObjectDetectionModel
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None


@dataclass
class ObjectDetectionModelInference:
    model: ObjectDetectionModelAdapters
    name: str
    description: str
    interval_seconds: float = 0.2

    def turn_on_prediction_loop(self):
        pass

    def turn_off_prediction_loop(self):
        pass

    def prediction_loop(self):
        pass

    def predict(self, frame: Frame):
        pass
