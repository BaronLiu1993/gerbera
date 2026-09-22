from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Literal, Protocol

from typing_extensions import TypeAlias

from gerbera_sdk.inference import (
    Frame,
    Inference,
    Model,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
    VisionLanguageModelInference,
)

InferenceType = Literal[
    "object_detection",
    "locate_object",
    "scene_analysis",
]
ModelOutput: TypeAlias = (
    PerceptionStateModel | VisionLanguageModelFrameEnvironment | str
)
InferenceResult: TypeAlias = ModelOutput | list[PerceptionStateModel]


class ModelSource(Protocol):
    models: list[Model]


class FrameSource(Protocol):
    def get_latest_frame(self, camera_key: str) -> Frame: ...


@dataclass
class ModelStream:
    stop_event: threading.Event
    thread: threading.Thread


@dataclass
class ModelRuntime:
    hardware_system: ModelSource
    camera_runtime: FrameSource
    model_outputs: dict[str, ModelOutput | None] = field(default_factory=dict)
    model_inferences: dict[str, Inference] = field(default_factory=dict)
    model_streams: dict[str, ModelStream] = field(default_factory=dict)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def register_models(self) -> None:
        with self.lock:
            if self.model_streams:
                raise RuntimeError(
                    "Cannot register models while model streams are active"
                )

        model_outputs: dict[str, ModelOutput | None] = {}
        model_inferences: dict[str, Inference] = {}
        for model in self.hardware_system.models:
            if model.model_id in model_inferences:
                raise ValueError(f"Duplicate model ID: {model.model_id}")
            for operation_keys in model.model_output_keys().values():
                for key in operation_keys.values():
                    if key in model_outputs:
                        raise ValueError(f"Duplicate model output key: {key}")
                    model_outputs[key] = None
            model_inferences[model.model_id] = model.create_inference()

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
            camera_ids = (
                [inference_input]
                if isinstance(inference_input, str)
                else inference_input
            )
            if not camera_ids:
                raise ValueError("At least one camera ID is required for inference")
            results = [
                self._predict_object_detection(inference, camera_id)
                for camera_id in camera_ids
            ]
            return results[0] if isinstance(inference_input, str) else results

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

    def _predict_object_detection(
        self,
        inference: ObjectDetectionModelInference,
        camera_id: str,
    ) -> PerceptionStateModel:
        if camera_id != inference.subscribed_camera.camera_id:
            raise RuntimeError(f"Camera is not subscribed: {camera_id}")
        frame = self.camera_runtime.get_latest_frame(camera_id)
        return inference.predict(frame)

    def is_model_running(self, model_id: str) -> bool:
        self.require_model_inference(model_id)
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
                raise RuntimeError(f"Model stream is already running: {model_id}")
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
                self.model_streams.pop(model_id)
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
                    self._predict_latest_object_detection(inference)
                elif isinstance(inference, VisionLanguageModelInference):
                    if prompt is None:
                        raise RuntimeError(
                            "Vision language model stream has no prompt"
                        )
                    self._predict_latest_vision_language(inference, prompt)
                else:
                    raise TypeError(
                        f"Unsupported inference type: {type(inference).__name__}"
                    )
                stop_event.wait(inference.interval_seconds)
        finally:
            with self.lock:
                stream = self.model_streams[model_id]
                if stream.thread is not threading.current_thread():
                    raise RuntimeError(
                        f"Model stream ownership changed while running: {model_id}"
                    )
                self.model_streams.pop(model_id)

    def _predict_latest_object_detection(
        self,
        inference: ObjectDetectionModelInference,
    ) -> None:
        camera_id = inference.subscribed_camera.camera_id
        frame = self.camera_runtime.get_latest_frame(camera_id)
        result = inference.predict(frame)
        self.write_model_output(
            key=inference.model_output_keys["object_detection"][camera_id],
            model_output=result,
        )

    def _predict_latest_vision_language(
        self,
        inference: VisionLanguageModelInference,
        prompt: str,
    ) -> None:
        camera = inference.subscribed_camera
        frame = self.camera_runtime.get_latest_frame(camera.camera_id)
        result = inference.predict(
            [frame],
            operation="locate_object",
            prompt=prompt,
        )
        self.write_model_output(
            key=inference.model_output_keys["locate_object"][camera.camera_id],
            model_output=result,
        )

    def turn_off_model_stream(self, model_id: str) -> None:
        self.require_model_inference(model_id)
        with self.lock:
            stream = self.model_streams.get(model_id)
        if stream is None:
            raise RuntimeError(f"Model stream is not running: {model_id}")

        stream.stop_event.set()
        stream.thread.join(timeout=5.0)
        if stream.thread.is_alive():
            raise RuntimeError(f"Model stream did not stop: {model_id}")

    def turn_on_all_model_streams(self) -> None:
        with self.lock:
            model_ids = list(self.model_inferences)

        started_model_ids: list[str] = []
        try:
            for model_id in model_ids:
                inference = self.require_model_inference(model_id)
                prompt = (
                    inference.user_prompt
                    if isinstance(inference, VisionLanguageModelInference)
                    else None
                )
                self.turn_on_model_stream(model_id, prompt=prompt)
                started_model_ids.append(model_id)
        except Exception:
            for model_id in reversed(started_model_ids):
                self.turn_off_model_stream(model_id)
            raise

    def turn_off_all_model_streams(self) -> None:
        with self.lock:
            model_ids = list(self.model_streams)
        for model_id in model_ids:
            self.turn_off_model_stream(model_id)
