from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import TypeAlias

from gerbera_sdk.inference import (
    Inference,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
    from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime

InferenceType = Literal[
    "object_detection",
    "locate_object",
    "scene_analysis",
]
ModelOutput: TypeAlias = (
    PerceptionStateModel | VisionLanguageModelFrameEnvironment | str
)
InferenceResult: TypeAlias = ModelOutput | list[PerceptionStateModel]


@dataclass
class ModelStream:
    stop_event: threading.Event
    thread: threading.Thread


@dataclass
class ModelRuntime:
    hardware_system: HardwareSystem
    camera_runtime: CameraRuntime
    model_outputs: dict[str, ModelOutput | None] = field(default_factory=dict)
    model_inferences: dict[str, Inference] = field(default_factory=dict)
    model_streams: dict[str, ModelStream] = field(default_factory=dict)
    harness_url: str = ""
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def register_models(self) -> None:
        model_outputs: dict[str, ModelOutput | None] = {}
        model_inferences: dict[str, Inference] = {}
        for model in self.hardware_system.models:
            for operation_keys in model.model_output_keys().values():
                for key in operation_keys.values():
                    model_outputs[key] = None
            model_inferences[model.model_id] = model.create_inference(
                model_output_writer=self,
                camera_runtime=self.camera_runtime,
            )

        with self.lock:
            self.model_outputs = model_outputs
            self.model_inferences = model_inferences

    def write_model_output(
        self,
        key: str,
        model_output: ModelOutput,
    ) -> None:
        with self.lock:
            if key not in self.model_outputs:
                raise KeyError(f"Model output is not registered: {key}")
            self.model_outputs[key] = model_output

    def read_model_output(
        self,
        model_id: str,
        camera_id: str,
        inference_type: InferenceType = "object_detection",
    ) -> ModelOutput:
        inference = self.require_model_inference(model_id)
        try:
            key = inference.model_output_keys[inference_type][camera_id]
        except KeyError as exc:
            raise RuntimeError(
                "Model output is not registered: "
                f"{model_id}.{camera_id}.{inference_type}"
            ) from exc

        with self.lock:
            model_output = self.model_outputs[key]
        if model_output is None:
            raise RuntimeError(
                "Model output has not been produced yet: "
                f"{model_id}.{camera_id}.{inference_type}"
            )
        return model_output

    @staticmethod
    def serialize_model_output(
        model_output: ModelOutput | None,
    ) -> Any:
        if model_output is None or isinstance(model_output, str):
            return model_output
        return model_output.model_dump(mode="json", exclude={"frame"})

    def get_model_state(self) -> dict[str, Any]:
        with self.lock:
            return {
                key: self.serialize_model_output(model_output)
                for key, model_output in self.model_outputs.items()
            }

    def require_model_inference(self, model_id: str) -> Inference:
        with self.lock:
            try:
                return self.model_inferences[model_id]
            except KeyError as exc:
                raise RuntimeError(
                    f"Model inference is not registered: {model_id}"
                ) from exc

    def single_inference(
        self,
        model_id: str,
        inference_type: InferenceType,
        inference_input: str | list[str],
        prompt: str | None = None,
    ) -> InferenceResult:
        inference = self.require_model_inference(model_id)
        if isinstance(inference, ObjectDetectionModelInference):
            if inference_type != "object_detection":
                raise TypeError(
                    f"Unsupported object detection operation: {inference_type}"
                )
            if isinstance(inference_input, str):
                return inference.predict(inference_input)
            return inference.predict_many(inference_input)

        if not isinstance(inference, VisionLanguageModelInference):
            raise TypeError(f"Unsupported inference type: {type(inference).__name__}")
        if inference_type not in ("locate_object", "scene_analysis"):
            raise TypeError(
                f"Unsupported vision language operation: {inference_type}"
            )
        if not isinstance(inference_input, list):
            raise TypeError(
                "Vision language inference requires a list of Base64 image strings"
            )
        if prompt is None:
            raise ValueError("Vision language model inference requires a prompt")

        result = inference.predict(
            inference_input,
            operation=inference_type,
            prompt=prompt,
        )
        camera_id = inference.subscribed_camera.camera_id
        self.write_model_output(
            key=inference.model_output_keys[inference_type][camera_id],
            model_output=result,
        )
        return result

    def is_model_running(self, model_id: str) -> bool:
        with self.lock:
            stream = self.model_streams.get(model_id)
            return stream is not None and stream.thread.is_alive()

    def turn_on_model_stream(
        self,
        model_id: str,
        prompt: str | None = None,
    ) -> None:
        inference = self.require_model_inference(model_id)
        if isinstance(inference, VisionLanguageModelInference) and prompt is None:
            raise ValueError("Vision language model stream requires a prompt")

        with self.lock:
            if self.is_model_running(model_id):
                return
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._prediction_loop,
                args=(model_id, inference, stop_event, prompt),
                name=f"model.{model_id}",
                daemon=False,
            )
            self.model_streams[model_id] = ModelStream(stop_event, thread)
            try:
                thread.start()
            except RuntimeError:
                self.model_streams.pop(model_id, None)
                raise

    def _prediction_loop(
        self,
        model_id: str,
        inference: Inference,
        stop_event: threading.Event,
        prompt: str | None,
    ) -> None:
        try:
            while not stop_event.is_set():
                if isinstance(inference, ObjectDetectionModelInference):
                    inference.predict_latest_frame()
                elif isinstance(inference, VisionLanguageModelInference):
                    if prompt is None:
                        raise RuntimeError(
                            "Vision language model stream has no prompt"
                        )
                    inference.predict_latest_frames(prompt)
                else:
                    raise TypeError(
                        f"Unsupported inference type: {type(inference).__name__}"
                    )
                stop_event.wait(inference.interval_seconds)
        finally:
            with self.lock:
                stream = self.model_streams.get(model_id)
                if (
                    stream is not None
                    and stream.thread is threading.current_thread()
                ):
                    self.model_streams.pop(model_id, None)

    def turn_off_model_stream(self, model_id: str) -> None:
        self.require_model_inference(model_id)
        with self.lock:
            stream = self.model_streams.get(model_id)
        if stream is None:
            return

        stream.stop_event.set()
        stream.thread.join(timeout=5.0)
        if stream.thread.is_alive():
            raise RuntimeError(f"Model stream did not stop: {model_id}")
        with self.lock:
            self.model_streams.pop(model_id, None)

    def turn_on_all_model_streams(self) -> None:
        with self.lock:
            model_ids = list(self.model_inferences)
        for model_id in model_ids:
            inference = self.require_model_inference(model_id)
            if isinstance(inference, VisionLanguageModelInference):
                continue
            self.turn_on_model_stream(model_id)

    def turn_off_all_model_streams(self) -> None:
        with self.lock:
            model_ids = list(self.model_streams)
        for model_id in model_ids:
            self.turn_off_model_stream(model_id)
