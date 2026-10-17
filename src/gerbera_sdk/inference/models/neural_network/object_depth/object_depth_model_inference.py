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
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_adapter import (
    DEFAULT_MAXIMUM_DEPTH_VALUES,
    OBJECT_DEPTH_MODEL_REGISTRY,
    ObjectDepthAdapter,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_schema import (
    ObjectDepthModelManifestSchema,
    ObjectDepthStateModel,
)
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema


class ObjectDepthModel(StrictSchema):
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1)
    model_directory: str = Field(min_length=1)
    subscribed_camera: Camera
    maximum_output_values: int = Field(
        default=DEFAULT_MAXIMUM_DEPTH_VALUES,
        gt=0,
    )
    description: str = ""
    model_type: Literal["object_depth"] = "object_depth"
    model_operations: ClassVar[tuple[Literal["object_depth"], ...]] = (
        "object_depth",
    )
    interval_seconds: float = Field(default=0.2, gt=0)

    def model_output_keys(self) -> dict[str, str]:
        return build_model_output_keys(
            self.model_id,
            self.subscribed_camera.camera_id,
            self.model_operations,
        )

    def create_inference(self) -> "ObjectDepthModelInference":
        manifest = ObjectDepthModelManifestSchema.model_validate(
            LocalModelFiles(self.model_directory).read_manifest()
        )
        adapter_class = OBJECT_DEPTH_MODEL_REGISTRY[manifest.model_format]
        adapter = adapter_class(
            model_directory=self.model_directory,
            manifest=manifest,
            maximum_output_values=self.maximum_output_values,
        )
        adapter.validate_configuration()
        return ObjectDepthModelInference(
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
class ObjectDepthModelInference:
    model: ObjectDepthAdapter
    name: str
    description: str
    subscribed_camera: Camera
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "object_depth"
    model_output_keys: dict[str, str] = field(default_factory=dict)
    interval_seconds: float = 0.2
    prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def predict(self, frame: Frame) -> ObjectDepthStateModel:
        with self.prediction_lock:
            return ObjectDepthStateModel(
                camera_id=self.subscribed_camera.camera_id,
                frame=frame,
                model_name=self.name,
                depth_map=self.model.estimate(frame),
            )
