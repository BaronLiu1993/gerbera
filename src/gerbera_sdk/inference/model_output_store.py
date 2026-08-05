from dataclasses import dataclass, field
import threading
from typing import TypeAlias

from gerbera_sdk.inference.model import Model
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)

ModelOutputStoreKey: TypeAlias = tuple[str, str]
ModelOutput: TypeAlias = PerceptionStateModel | VisionLanguageModelFrameEnvironment


@dataclass
class ModelOutputStore:
    model_outputs: dict[ModelOutputStoreKey, ModelOutput | None] = field(
        default_factory=dict
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def _require_registered(self, key: ModelOutputStoreKey) -> None:
        if key not in self.model_outputs:
            raise KeyError(f"Model output is not registered: {key}")

    def register_models(self, models: list[Model]) -> None:
        with self._lock:
            for model in models:
                for camera in model.subscribed_cameras:
                    key = (camera.camera_id, model.model_id)
                    if key in self.model_outputs:
                        raise KeyError(f"Model output is already registered: {key}")
                    self.model_outputs[key] = None

    def write_model_output(
        self,
        camera_id: str,
        model_id: str,
        model_output: ModelOutput,
    ) -> None:
        key = (camera_id, model_id)
        with self._lock:
            self._require_registered(key)
            self.model_outputs[key] = model_output

    def read_model_output(
        self,
        camera_id: str,
        model_id: str,
    ) -> ModelOutput:
        key = (camera_id, model_id)
        with self._lock:
            self._require_registered(key)
            model_output = self.model_outputs[key]
            if model_output is None:
                raise RuntimeError(
                    f"Registered model has not produced an output: {key}"
                )

            return model_output
