from dataclasses import dataclass, field
import threading
from typing import Any, Union

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)

ModelOutput = Union[PerceptionStateModel, VisionLanguageModelFrameEnvironment, str]


@dataclass
class ModelOutputStore:
    model_outputs: dict[str, ModelOutput | None] = field(
        default_factory=dict
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def require_registered(self, key: str) -> None:
        if key not in self.model_outputs:
            raise KeyError(f"Model output is not registered: {key}")

    def register(self, keys: list[str]) -> None:
        for key in dict.fromkeys(keys):
            self.model_outputs.setdefault(key, None)

    def write_model_output(
        self,
        key: str,
        model_output: ModelOutput,
    ) -> None:
        with self._lock:
            self.require_registered(key)
            self.model_outputs[key] = model_output

    def read_model_output(
        self,
        key: str,
    ) -> ModelOutput:
        with self._lock:
            self.require_registered(key)
            model_output = self.model_outputs[key]
            if model_output is None:
                raise RuntimeError(
                    f"Registered model has not produced an output: {key}"
                )

            return model_output

    def get_environment_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                key: (
                    None
                    if model_output is None
                    else model_output
                    if isinstance(model_output, str)
                    else model_output.model_dump(
                        mode="json",
                        exclude={"frame"},
                    )
                )
                for key, model_output in self.model_outputs.items()
            }
