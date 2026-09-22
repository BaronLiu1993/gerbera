from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Literal
import uuid

from pydantic import Field

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    OBJECT_DETECTION_MODEL_REGISTRY,
    ObjectDetectionModelAdapters,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.model_types import ObjectDetectionModelProviderEnum
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema, build_hashable_key


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
    model_operations: tuple[Literal["object_detection"], ...] = (
        "object_detection",
    )
    interval_seconds: float = Field(default=0.2, gt=0)

    def model_output_keys(self) -> dict[str, dict[str, str]]:
        camera_id = self.subscribed_camera.camera_id
        return {
            "object_detection": {
                camera_id: build_hashable_key(
                    self.model_id,
                    camera_id,
                    "object_detection",
                )
            }
        }

    def create_inference(
        self,
        model_output_writer: Any,
        camera_runtime: Any,
    ) -> "ObjectDetectionModelInference":
        adapter_class = OBJECT_DETECTION_MODEL_REGISTRY[self.model_name]
        adapter = adapter_class(
            model_source=self.model_source,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            max_detections=self.max_detections,
        )
        return ObjectDetectionModelInference(
            model=adapter,
            model_output_writer=model_output_writer,
            camera_runtime=camera_runtime,
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
    model: ObjectDetectionModelAdapters
    model_output_writer: Any
    camera_runtime: Any
    name: str
    description: str
    subscribed_camera: Camera
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "object_detection"
    model_output_keys: dict[str, dict[str, str]] = field(default_factory=dict)
    interval_seconds: float = 0.2
    _prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @property
    def subscribed_cameras(self) -> list[Camera]:
        return [self.subscribed_camera]

    def predict_for_frame(
        self,
        camera: Camera,
        frame: Frame,
    ) -> PerceptionStateModel:
        return PerceptionStateModel(
            camera_id=camera.camera_id,
            frame=frame,
            model_name=self.name,
            perception_objects=self.model.detect(frame),
        )

    def predict(self, camera_id: str) -> PerceptionStateModel:
        if camera_id != self.subscribed_camera.camera_id:
            raise RuntimeError(f"Camera is not subscribed: {camera_id}")
        frame = self.camera_runtime.get_latest_frame(camera_id)
        with self._prediction_lock:
            return self.predict_for_frame(self.subscribed_camera, frame)

    def predict_many(self, camera_ids: list[str]) -> list[PerceptionStateModel]:
        if not camera_ids:
            raise ValueError("At least one camera ID is required for inference")
        return [self.predict(camera_id) for camera_id in camera_ids]

    def predict_latest_frame(self) -> None:
        camera_id = self.subscribed_camera.camera_id
        with self.camera_runtime.lock:
            frame = self.camera_runtime.latest_frames.get(camera_id)
        if frame is None:
            return
        with self._prediction_lock:
            result = self.predict_for_frame(self.subscribed_camera, frame)
        self.model_output_writer.write_model_output(
            key=self.model_output_keys["object_detection"][camera_id],
            model_output=result,
        )
