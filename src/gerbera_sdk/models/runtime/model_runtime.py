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
class ModelRuntime:
    hardware_system: HardwareSystem
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @cached_property
    def model_output_store(self) -> ModelOutputStore:
        store = ModelOutputStore()
        keys = [
            (camera.camera_id, model.model_id)
            for model in self.hardware_system.models
            for camera in model.subscribed_cameras
        ]
        store.register(keys)
        return store

    @cached_property
    def model_inferences(self) -> dict[str, Inference]:
        return {
            model.model_id: model.create_inference(self.model_output_store)
            for model in self.hardware_system.models
        }

    def read_model_output(self, model_id: str, camera_id: str) -> object:
        return self.model_output_store.read_model_output(
            model_id=model_id, camera_id=camera_id
        )

    def single_inference(
        self,
        model_id: str,
        inference_input: str | list[str],
    ) -> PerceptionStateModel | VisionLanguageModelFrameEnvironment:
        inference = self.model_inferences[model_id]

        if isinstance(inference, ObjectDetectionModelInference):
            if not isinstance(inference_input, str):
                raise TypeError(
                    "Object detection inference requires a camera ID"
                )
            return inference.predict(inference_input)

        if isinstance(inference, VisionLanguageModelInference):
            if not isinstance(inference_input, list) or not all(
                isinstance(frame, str) for frame in inference_input
            ):
                raise TypeError(
                    "Vision language model inference requires a list of "
                    "Base64 image strings"
                )
            return inference.predict(inference_input)

        raise TypeError(f"Unsupported inference type: {type(inference).__name__}")

    def turn_on_model(self, model_id: str) -> None:
        with self._lock:
            inference = self.model_inferences[model_id]
            if inference.is_running:
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
