from dataclasses import dataclass, field
import threading
from typing import Any, Union

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)

ModelOutput = Union[PerceptionStateModel, VisionLanguageModelFrameEnvironment]


@dataclass
class ModelOutputStore:
    model_outputs: dict[tuple[str, str], ModelOutput | None] = field(
        default_factory=dict
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def _require_registered(self, key: tuple[str, str]) -> None:
        if key not in self.model_outputs:
            raise KeyError(f"Model output is not registered: {key}")

    def register(self, keys: list[tuple[str, str]]) -> None:
        with self._lock:
            if len(keys) != len(set(keys)):
                raise KeyError("Model output key is registered more than once")

            duplicate_keys = set(keys) & self.model_outputs.keys()
            if duplicate_keys:
                duplicate_key = duplicate_keys.pop()
                raise KeyError(f"Model output is already registered: {duplicate_key}")

            for key in keys:
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

    def get_environment_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                f"{camera_id}::{model_id}": (
                    None
                    if model_output is None
                    else model_output.model_dump(
                        mode="json",
                        exclude={"frame"},
                    )
                )
                for (camera_id, model_id), model_output in self.model_outputs.items()
            }
