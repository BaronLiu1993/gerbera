from dataclasses import dataclass, field
from typing import Any, TypeAlias, Union
import threading

from gerbera_sdk.inference import (
    Inference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
)

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.utils import build_hashable_key

ModelOutput: TypeAlias = Union[
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    str,
]


@dataclass
class ModelRuntime:
    hardware_system: HardwareSystem
    model_outputs: dict[str, ModelOutput | None] = field(default_factory=dict)
    # this holds the model object that will be registered and the
    model_inferences: dict[str, Inference] = field(default_factory=dict)
    harness_url: str = ""  # optional parameter
    lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    # each model has their own keys that they can perform and that will differentiate them e.g. scene_analysis, object detection
    def register_models(self) -> None:
        for model in self.hardware_system.models:
            for operation in model.model_operations:
                key = build_hashable_key(
                    model.model_name,
                    model.model_type,
                    model.subscribed_camera.camera_id,
                    operation,
                )
                self.model_outputs[key] = None
            self.model_inferences[model.model_id] = model.create_inference(self)

    # read, write methods
    def write_model_output(
        self,
        model_name: str,
        model_type: str,
        camera_id: str,
        operation: str,
        model_output: ModelOutput,
    ) -> None:
        key = build_hashable_key(
            model_name,
            model_type,
            camera_id,
            operation,
        )
        with self.lock:
            if key in self.model_outputs:
                self.model_outputs[key] = model_output

    def read_model_output(
        self,
        model_name: str,
        model_type: str,
        camera_id: str,
        operation: str,
    ) -> ModelOutput | None:
        key = build_hashable_key(
            model_name,
            model_type,
            camera_id,
            operation,
        )
        with self.lock:
            if key in self.model_outputs:
                model_output = self.model_outputs[key]
                return model_output

    # Get the entire state
    # Handle literal frames, None, or if it is just a string right now
    def serialize_model_output(
        self,
        model_output: ModelOutput | None,
    ) -> Any:
        if isinstance(model_output, None):
            return None
        if isinstance(model_output, str):
            return model_output

        return model_output.model_dump(
            mode="json",
            exclude={"frame"},
        )

    def get_model_state(self) -> dict[str, Any]:
        with self.lock:
            return {
                key: self.serialize_model_output(model_output)
                for key, model_output in self.model_outputs.items()
            }

    def single_inference(
        self,
        model_id: str,
        inference_type: InferenceType,
        inference_input: str | list[str],
        prompt: str | None = None,
    ):
        inference = self.model_inferences[model_id]
        for strategy in SINGLE_INFERENCE_STRATEGIES:
            if strategy.supports(
                inference_type=inference_type,
                inference=inference,
            ):
                return strategy.run(
                    runtime=self,
                    model_id=model_id,
                    inference=inference,
                    inference_input=inference_input,
                    prompt=prompt,
                )

        raise TypeError(f"Unsupported inference type: {type(inference).__name__}")

    def require_model_inference(self, model_id: str) -> Inference:
        with self._lock:
            try:
                return self.model_inferences[model_id]
            except KeyError as exc:
                raise RuntimeError(
                    f"Model inference is not registered: {model_id}"
                ) from exc

    def require_model_stream_strategy(
        self,
        inference: Inference,
    ) -> ModelStreamStrategy:
        for strategy in MODEL_STREAM_STRATEGIES:
            if strategy.supports(inference):
                return strategy
        raise TypeError(f"Unsupported inference type: {type(inference).__name__}")

    def model_stream(
        self,
        model_id: str,
        action: ModelStreamAction,
        prompt: str | None = None,
    ) -> None:
        inference = self.require_model_inference(model_id)
        strategy = self.require_model_stream_strategy(inference)
        strategy.run(
            inference=inference,
            action=action,
            prompt=prompt,
        )
