from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, TypeAlias, Union
import threading

from gerbera_sdk.inference import (
    Inference,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
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
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _model_output_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def register_model_output_keys(self) -> None:
        keys: list[str] = []
        for model in self.hardware_system.models:
            for camera in model.subscribed_cameras:
                keys.append(
                    (
                        f"{camera.name}."
                        f"{model.name}."
                        f"{model.model_type}."
                        f"{model.output_field}"
                    )
                )
        self.register_model_outputs(keys)

    @cached_property
    def model_inferences(self) -> dict[str, Inference]:
        self.register_model_output_keys()
        return {
            model.model_id: model.create_inference(self)
            for model in self.hardware_system.models
        }

    def require_registered_model_output(self, key: str) -> None:
        if key not in self.model_outputs:
            raise KeyError(f"Model output is not registered: {key}")

    def register_model_outputs(self, keys: list[str]) -> None:
        with self._model_output_lock:
            for key in dict.fromkeys(keys):
                self.model_outputs.setdefault(key, None)

    def write_model_output(
        self,
        key: str,
        model_output: ModelOutput,
    ) -> None:
        with self._model_output_lock:
            self.require_registered_model_output(key)
            self.model_outputs[key] = model_output

    def read_model_output_by_key(
        self,
        key: str,
    ) -> ModelOutput:
        with self._model_output_lock:
            self.require_registered_model_output(key)
            model_output = self.model_outputs[key]
            if model_output is None:
                raise RuntimeError(
                    f"Registered model has not produced an output: {key}"
                )

            return model_output

    def get_environment_state(self) -> dict[str, Any]:
        self.register_model_output_keys()
        with self._model_output_lock:
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

    def read_model_output(
        self,
        model_id: str,
        camera_id: str,
        output_field: str | None = None,
    ) -> object:
        self.register_model_output_keys()
        for model in self.hardware_system.models:
            if model.model_id != model_id:
                continue
            for camera in model.subscribed_cameras:
                if camera.camera_id != camera_id:
                    continue
                selected_output_field = output_field or model.output_field
                if model.model_type == "vision_language_model":
                    selected_output_field = output_field or "scene_objects"
                return self.read_model_output_by_key(
                    (
                        f"{camera.name}."
                        f"{model.name}."
                        f"{model.model_type}."
                        f"{selected_output_field}"
                    )
                )

        raise RuntimeError(f"Model output is not registered: {camera_id}, {model_id}")

    def write_model_output_for_subscribed_cameras(
        self,
        model_id: str,
        output_field: str,
        model_output: object,
    ) -> None:
        for model in self.hardware_system.models:
            if model.model_id != model_id:
                continue
            for camera in model.subscribed_cameras:
                self.write_model_output(
                    key=(
                        f"{camera.name}."
                        f"{model.name}."
                        f"{model.model_type}."
                        f"{output_field}"
                    ),
                    model_output=model_output,
                )
            return

        raise RuntimeError(f"Model output is not registered: {model_id}")

    def single_inference(
        self,
        model_id: str,
        inference_input: str | list[str],
        prompt: str | None = None,
    ) -> (
        list[PerceptionStateModel]
        | VisionLanguageModelFrameEnvironment
    ):
        inference = self.model_inferences[model_id]

        if isinstance(inference, ObjectDetectionModelInference):
            if isinstance(inference_input, str):
                return inference.predict(inference_input)
            if not isinstance(inference_input, list) or not all(
                isinstance(camera_id, str)
                for camera_id in inference_input
            ):
                raise TypeError(
                    "Object detection inference requires one camera ID or "
                    "a list of camera IDs"
                )
            if not inference_input:
                raise ValueError(
                    "At least one camera ID is required for inference"
                )
            return inference.predict_many(inference_input)

        if isinstance(inference, VisionLanguageModelInference):
            if prompt is None:
                raise ValueError(
                    "Vision language model inference requires a prompt"
                )
            if not isinstance(inference_input, list) or not all(
                isinstance(frame, str) for frame in inference_input
            ):
                raise TypeError(
                    "Vision language model inference requires a list of "
                    "Base64 image strings"
                )
            result = inference.predict(inference_input, prompt=prompt)
            self.write_model_output_for_subscribed_cameras(
                model_id=model_id,
                output_field=inference.scene_objects_output_field,
                model_output=result,
            )
            return result

        raise TypeError(f"Unsupported inference type: {type(inference).__name__}")

    def analyze_scene(
        self,
        model_id: str,
        frames: list[str],
        prompt: str,
    ) -> str:
        inference = self.model_inferences[model_id]
        if not isinstance(inference, VisionLanguageModelInference):
            raise TypeError(
                "Scene analysis requires a vision language model inference"
            )
        if not all(isinstance(frame, str) for frame in frames):
            raise TypeError(
                "Scene analysis requires a list of Base64 image strings"
            )

        result = inference.analyze_scene(frames, prompt=prompt)
        self.write_model_output_for_subscribed_cameras(
            model_id=model_id,
            output_field=inference.scene_analysis_output_field,
            model_output=result,
        )
        return result

    def turn_on_model(self, model_id: str, prompt: str | None = None) -> None:
        with self._lock:
            inference = self.model_inferences[model_id]
            if inference.is_running:
                return
            if isinstance(inference, VisionLanguageModelInference):
                if prompt is None:
                    raise ValueError(
                        "Vision language model prediction loop requires a prompt"
                    )
                inference.turn_on_prediction_loop(prompt=prompt)
                return
            inference.turn_on_prediction_loop()

    def turn_off_model(self, model_id: str) -> None:
        with self._lock:
            inference = self.model_inferences[model_id]
            if not inference.is_running:
                return
            inference.turn_off_prediction_loop()

    def turn_on_all_models(self) -> None:
        with self._lock:
            started: list[Inference] = []
            try:
                for inference in self.model_inferences.values():
                    if inference.is_running:
                        continue
                    if isinstance(inference, VisionLanguageModelInference):
                        raise ValueError(
                            "Vision language model prediction loop requires a prompt"
                        )
                    inference.turn_on_prediction_loop()
                    started.append(inference)
            except Exception:
                for inference in reversed(started):
                    inference.turn_off_prediction_loop()
                raise

    def turn_off_all_models(self) -> None:
        with self._lock:
            errors: list[Exception] = []
            for inference in reversed(self.model_inferences.values()):
                if not inference.is_running:
                    continue
                try:
                    inference.turn_off_prediction_loop()
                except Exception as exc:
                    errors.append(exc)

            if errors:
                raise RuntimeError("Could not stop all model inferences") from errors[0]
