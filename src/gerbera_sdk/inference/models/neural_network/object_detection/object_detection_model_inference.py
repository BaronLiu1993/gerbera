from dataclasses import dataclass, field
import threading
from typing import ClassVar, Literal
import uuid

from pydantic import Field

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    OBJECT_DETECTION_MODEL_REGISTRY,
    ObjectDetectionAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.model_types import (
    ObjectDetectionModelProviderEnum,
    build_model_output_keys,
)
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema


class ObjectDetectionModel(StrictSchema):
    model_name: ObjectDetectionModelProviderEnum
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1)
    model_source: str = Field(min_length=1)
    subscribed_camera: Camera
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    max_detections: int = 300
    description: str = ""
    model_type: Literal["object_detection"] = "object_detection"
    model_operations: ClassVar[tuple[Literal["object_detection"], ...]] = (
        "object_detection",
    )
    interval_seconds: float = Field(default=0.2, gt=0)

    def model_output_keys(self) -> dict[str, str]:
        return build_model_output_keys(
            self.model_id,
            self.subscribed_camera.camera_id,
            self.model_operations,
        )

    def create_inference(self) -> "ObjectDetectionModelInference":
        adapter_class = OBJECT_DETECTION_MODEL_REGISTRY[self.model_name]
        adapter = adapter_class(
            model_source=self.model_source,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            max_detections=self.max_detections,
        )
        return ObjectDetectionModelInference(
            model=adapter,
            name=self.name,
            description=self.description,
            subscribed_camera=self.subscribed_camera,
            model_output_keys=self.model_output_keys(),
            interval_seconds=self.interval_seconds,
            model_id=self.model_id,
            model_type=self.model_type,
        )


@dataclass
class ObjectDetectionModelInference:
    model: ObjectDetectionAdapter
    name: str
    description: str
    subscribed_camera: Camera
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "object_detection"
    model_output_keys: dict[str, str] = field(default_factory=dict)
    interval_seconds: float = 0.2
    _prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def predict(self, frame: Frame) -> PerceptionStateModel:
        with self._prediction_lock:
            return PerceptionStateModel(
                camera_id=self.subscribed_camera.camera_id,
                frame=frame,
                model_name=self.name,
                perception_objects=self.model.detect(frame),
            )
