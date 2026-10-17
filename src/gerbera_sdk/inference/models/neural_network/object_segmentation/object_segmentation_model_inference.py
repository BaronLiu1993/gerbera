from dataclasses import dataclass, field
import threading
from typing import ClassVar, Literal
import uuid

from pydantic import Field

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.neural_network.local_model_files import (
    LocalModelFiles,
)
from gerbera_sdk.inference.model_types import build_model_output_keys
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_adapter import (
    OBJECT_SEGMENTATION_MODEL_REGISTRY,
    ObjectSegmentationAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_schema import (
    ObjectSegmentationModelManifestSchema,
    ObjectSegmentationStateModel,
)
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema


class ObjectSegmentationModel(StrictSchema):
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1)
    model_directory: str = Field(min_length=1)
    subscribed_camera: Camera
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    mask_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_detections: int = Field(default=100, gt=0)
    description: str = ""
    model_type: Literal["object_segmentation"] = "object_segmentation"
    model_operations: ClassVar[
        tuple[Literal["object_segmentation"], ...]
    ] = ("object_segmentation",)
    interval_seconds: float = Field(default=0.2, gt=0)

    def model_output_keys(self) -> dict[str, str]:
        return build_model_output_keys(
            self.model_id,
            self.subscribed_camera.camera_id,
            self.model_operations,
        )

    def create_inference(self) -> "ObjectSegmentationModelInference":
        manifest = ObjectSegmentationModelManifestSchema.model_validate(
            LocalModelFiles(self.model_directory).read_manifest()
        )
        adapter_class = OBJECT_SEGMENTATION_MODEL_REGISTRY[
            manifest.model_format
        ]
        adapter = adapter_class(
            model_directory=self.model_directory,
            manifest=manifest,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            mask_threshold=self.mask_threshold,
            max_detections=self.max_detections,
        )
        adapter.validate_configuration()
        return ObjectSegmentationModelInference(
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
class ObjectSegmentationModelInference:
    model: ObjectSegmentationAdapter
    name: str
    description: str
    subscribed_camera: Camera
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "object_segmentation"
    model_output_keys: dict[str, str] = field(default_factory=dict)
    interval_seconds: float = 0.2
    prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def predict(self, frame: Frame) -> ObjectSegmentationStateModel:
        with self.prediction_lock:
            return ObjectSegmentationStateModel(
                camera_id=self.subscribed_camera.camera_id,
                frame=frame,
                model_name=self.name,
                segmented_objects=self.model.segment(frame),
            )
