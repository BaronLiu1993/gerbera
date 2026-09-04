from dataclasses import dataclass, field
from typing import Any, TypeAlias, Union
import threading

from gerbera_sdk.inference import (
    Inference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.inference_strategy import (
    InferenceType,
    InferenceStrategyResult,
    MODEL_STREAM_STRATEGIES,
    ModelStreamAction,
    ModelStreamStrategy,
    SINGLE_INFERENCE_STRATEGIES,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem

ModelOutput: TypeAlias = Union[
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    str,
]


@dataclass
class EnvironmentRuntime:
    hardware_system: HardwareSystem
    model_outputs: dict[str, ModelOutput | None] = field(default_factory=dict)
    model_inferences: dict[str, Inference] = field(default_factory=dict)
    harness_url: str = ""
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def register_model_inferences(self) -> None:
        model_outputs: dict[str, ModelOutput | None] = {}
        model_inferences: dict[str, Inference] = {}

        for model in self.hardware_system.models:
            for model_output_keys in model.model_output_keys().values():
                for key in model_output_keys.values():
                    model_outputs.setdefault(key, None)
            model_inferences[model.model_id] = model.create_inference(self)

        with self._lock:
            self.model_outputs = model_outputs
            self.model_inferences = model_inferences

    def require_registered_model_output(self, key: str) -> None:
        if key not in self.model_outputs:
            raise KeyError(f"Model output is not registered: {key}")

    # read, write methods
    def write_model_output(
        self,
        key: str,
        model_output: ModelOutput,
    ) -> None:
        with self._lock:
            self.require_registered_model_output(key)
            self.model_outputs[key] = model_output

    def read_model_output_by_key(
        self,
        key: str,
    ) -> ModelOutput | None:
        with self._lock:
            self.require_registered_model_output(key)
            model_output = self.model_outputs[key]
            return model_output

    def read_model_output(
        self,
        model_id: str,
        camera_id: str,
        inference_type: InferenceType = "object_detection",
    ) -> ModelOutput:
        model = next(
            (
                model
                for model in self.hardware_system.models
                if model.model_id == model_id
            ),
            None,
        )
        if model is None:
            raise RuntimeError(f"Model output is not registered: {model_id}")

        camera = next(
            (
                camera
                for camera in model.subscribed_cameras
                if camera.camera_id == camera_id
            ),
            None,
        )
        if camera is None:
            raise RuntimeError(
                f"Camera is not subscribed to model: {model_id}.{camera_id}"
            )

        model_output = self.read_model_output_by_key(
            model.model_output_keys()[inference_type][camera.camera_id]
        )
        if model_output is None:
            raise RuntimeError(
                "Model output has not been produced yet: "
                f"{model_id}.{camera_id}"
            )
        return model_output

    # Get the entire state
    # Handle literal frames, None, or if it is just a string right now
    def serialize_model_output(
        self,
        model_output: ModelOutput | None,
    ) -> Any:
        if model_output is None:
            return None
        if isinstance(model_output, str):
            return model_output
        return model_output.model_dump(
            mode="json",
            exclude={"frame"},
        )

    def get_environment_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                key: self.serialize_model_output(model_output)
                for key, model_output in self.model_outputs.items()
            }

    def write_model_output_for_subscribed_cameras(
        self,
        model_id: str,
        inference_type: InferenceType,
        model_output: object,
    ) -> None:
        for model in self.hardware_system.models:
            if model.model_id != model_id:
                continue

            model_output_keys = model.model_output_keys()[inference_type]
            for camera in model.subscribed_cameras:
                self.write_model_output(
                    key=model_output_keys[camera.camera_id],
                    model_output=model_output,
                )
            return

        raise RuntimeError(f"Model output is not registered: {model_id}")

    def single_inference(
        self,
        model_id: str,
        inference_type: InferenceType,
        inference_input: str | list[str],
        prompt: str | None = None,
    ) -> InferenceStrategyResult:
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

    def turn_on_model_stream(
        self,
        model_id: str,
        prompt: str | None = None,
    ) -> None:
        self._model_stream(model_id=model_id, action="on", prompt=prompt)

    def turn_off_model_stream(self, model_id: str) -> None:
        self._model_stream(model_id=model_id, action="off")

    def _model_stream(
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

    def turn_on_all_model_streams(self) -> None:
        self._apply_model_streams(action="on")

    def turn_off_all_model_streams(self) -> None:
        self._apply_model_streams(action="off")

    def _apply_model_streams(self, action: ModelStreamAction) -> None:
        with self._lock:
            inferences = list(self.model_inferences.values())

        started: list[Inference] = []
        try:
            for inference in inferences:
                strategy = self.require_model_stream_strategy(inference)
                if action == "on" and strategy.requires_prompt_to_turn_on:
                    continue

                was_running = inference.is_running
                strategy.run(
                    inference=inference,
                    action=action,
                    prompt=None,
                )
                if action == "on" and not was_running and inference.is_running:
                    started.append(inference)
        except Exception:
            for inference in reversed(started):
                inference.turn_off_prediction_loop()
            raise
