from dataclasses import dataclass, field
from functools import cached_property
import threading

from gerbera_sdk.inference import (
    Inference,
    ModelOutputStore,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class EnvironmentRuntime:
    hardware_system: HardwareSystem
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @cached_property
    def model_output_store(self) -> ModelOutputStore:
        store = ModelOutputStore()
        keys: list[str] = []
        for model in self.hardware_system.models:
            for camera in model.subscribed_cameras:
                if model.model_type == "vision_language_model":
                    keys.append(
                        (
                            f"{camera.name}."
                            f"{model.name}."
                            f"{model.model_type}."
                            "scene_objects"
                        )
                    )
                    keys.append(
                        (
                            f"{camera.name}."
                            f"{model.name}."
                            f"{model.model_type}."
                            "scene_analysis"
                        )
                    )
                    continue
                keys.append(
                    (
                        f"{camera.name}."
                        f"{model.name}."
                        f"{model.model_type}."
                        f"{model.output_field}"
                    )
                )
        store.register(keys)
        return store

    @cached_property
    def model_inferences(self) -> dict[str, Inference]:
        return {
            model.model_id: model.create_inference(self.model_output_store)
            for model in self.hardware_system.models
        }

    def read_model_output(
        self,
        model_id: str,
        camera_id: str,
        output_field: str | None = None,
    ) -> object:
        for model in self.hardware_system.models:
            if model.model_id != model_id:
                continue
            for camera in model.subscribed_cameras:
                if camera.camera_id != camera_id:
                    continue
                selected_output_field = output_field or model.output_field
                if model.model_type == "vision_language_model":
                    selected_output_field = output_field or "scene_objects"
                return self.model_output_store.read_model_output(
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
                self.model_output_store.write_model_output(
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
