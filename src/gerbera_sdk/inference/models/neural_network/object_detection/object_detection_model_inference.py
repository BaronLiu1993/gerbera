from dataclasses import dataclass, field

from pydantic import Field, InstanceOf
import threading
import uuid

from gerbera_sdk.inference.model_output_store import ModelOutputStore
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    OBJECT_DETECTION_MODEL_REGISTRY,
    ObjectDetectionModelAdapters,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.model_types import (
    ObjectDetectionModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera


@dataclass
class ObjectDetectionModel:
    model_id: str = field(
        default_factory=lambda: str(uuid.uuid4()),
        init=False,
    )
    model_name: ObjectDetectionModelProviderEnum
    name: str = Field(min_length=1)
    model_source: str = Field(min_length=1)
    subscribed_cameras: list[InstanceOf[Camera]] = Field(min_length=1)
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    max_detections: int = 300
    description: str = ""

    def create_inference(
        self,
        model_output_store: ModelOutputStore,
    ) -> "ObjectDetectionModelInference":
        adapter_class = OBJECT_DETECTION_MODEL_REGISTRY[self.model_name]
        object_detection_model = adapter_class(
            model_source=self.model_source,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            max_detections=self.max_detections,
        )

        return ObjectDetectionModelInference(
            model_session=ObjectDetectionSession(
                model=object_detection_model,
                model_output_store=model_output_store,
            ),
            name=self.name,
            description=self.description,
            subscribed_cameras=self.subscribed_cameras,
            model_id=self.model_id,
        )


@dataclass
class ObjectDetectionSession:
    model: ObjectDetectionModelAdapters
    model_output_store: ModelOutputStore
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None


@dataclass
class ObjectDetectionModelInference:
    model_session: ObjectDetectionSession
    name: str
    description: str
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscribed_cameras: list[Camera] = field(default_factory=list)
    interval_seconds: float = 0.2
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @property
    def is_running(self) -> bool:
        with self._lock:
            thread = self.model_session._thread
            stop_event = self.model_session._stop_event
            if (thread is None) != (stop_event is None):
                raise RuntimeError("Object detection thread state is invalid")
            return thread is not None

    def turn_on_prediction_loop(self) -> None:
        with self._lock:
            if (
                self.model_session._thread is not None
                or self.model_session._stop_event is not None
            ):
                raise RuntimeError(
                    f"Object detection is already running: {self.name}"
                )

            stop_event = threading.Event()
            thread = threading.Thread(
                target=self.prediction_loop,
                name=f"object-detection-{self.name}",
                daemon=False,
            )
            self.model_session._stop_event = stop_event
            self.model_session._thread = thread

            try:
                thread.start()
            except RuntimeError as exc:
                self.model_session._stop_event = None
                self.model_session._thread = None
                raise RuntimeError(
                    f"Could Not Start Object Detection Thread {self.name}"
                ) from exc

    def turn_off_prediction_loop(self) -> None:
        with self._lock:
            stop_event = self.model_session._stop_event
            thread = self.model_session._thread
            if stop_event is None or thread is None:
                raise RuntimeError(
                    f"Object detection is not running: {self.name}"
                )

            stop_event.set()
            thread.join(timeout=5.0)
            if thread.is_alive():
                raise RuntimeError(
                    f"Object detection thread did not stop: {self.name}"
                )

            self.model_session._stop_event = None
            self.model_session._thread = None

    def predict(self, camera: Camera) -> PerceptionStateModel:
        frame = camera.latest_frame
        if frame is None:
            raise RuntimeError(f"Camera has no frame: {camera.camera_id}")

        perception_objects = self.model_session.model.detect(frame)
        return PerceptionStateModel(
            camera_id=camera.camera_id,
            frame=frame,
            model_name=self.name,
            perception_objects=perception_objects,
        )

    def prediction_loop(self) -> None:
        stop_event = self.model_session._stop_event
        if stop_event is None:
            raise RuntimeError("Object detection prediction loop has no stop event")

        while not stop_event.is_set():
            for camera in self.subscribed_cameras:
                if camera.latest_frame is not None:
                    perception_state = self.predict(camera)
                    self.model_session.model_output_store.write_model_output(
                        camera_id=camera.camera_id,
                        model_id=self.model_id,
                        model_output=perception_state,
                    )

            stop_event.wait(self.interval_seconds)
