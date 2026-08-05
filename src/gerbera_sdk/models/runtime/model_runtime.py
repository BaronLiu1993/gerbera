from dataclasses import dataclass, field
import threading

from gerbera_sdk.inference import Inference, ModelOutputStore
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class ModelRuntime:
    hardware_system: HardwareSystem
    
    _started: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @property
    def model_inferences(self) -> list[Inference]:
        models = self.hardware_system.models
        return [model.create_inference(self.model_output_store) for model in models]

    @property
    def model_output_store(self) -> ModelOutputStore:
        models = self.hardware_system.models

        store = ModelOutputStore()
        keys = [
            (camera.camera_id, model.model_id)
            for model in models
            for camera in model.subscribed_cameras
        ]
        store.register(keys)
        return store

    # def start(self) -> None:
    #     with self._lock:
    #         if self._started:
    #             raise RuntimeError("Model runtime is already started")

    #         started: list[Inference] = []
    #         try:
    #             for inference in self.model_inferences:
    #                 inference.turn_on_prediction_loop()
    #                 started.append(inference)
    #         except Exception:
    #             for inference in reversed(started):
    #                 inference.turn_off_prediction_loop()
    #             raise

    #         self._started = True

    # def stop(self) -> None:
    #     with self._lock:
    #         if not self._started:
    #             raise RuntimeError("Model runtime is not started")

    #         errors: list[Exception] = []
    #         for inference in reversed(self.model_inferences):
    #             if not inference.is_running:
    #                 continue
    #             try:
    #                 inference.turn_off_prediction_loop()
    #             except Exception as exc:
    #                 errors.append(exc)

    #         if errors:
    #             raise RuntimeError("Could not stop all model inferences") from errors[0]

    #         self._started = False

    # def turn_on_inference(self, inference: Inference) -> None:
    #     with self._lock:
    #         if not self._started:
    #             raise RuntimeError("Model runtime is not started")
    #         inference.turn_on_prediction_loop()

    # def turn_off_inference(self, inference: Inference) -> None:
    #     with self._lock:
    #         if not self._started:
    #             raise RuntimeError("Model runtime is not started")
    #         inference.turn_off_prediction_loop()
