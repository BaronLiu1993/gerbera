from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
import threading
from typing import Any, Callable

from typing_extensions import TypeAlias

from gerbera_sdk.inference import (
    Inference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.model_runtime_strategies import (
    MODEL_RUNTIME_STRATEGIES,
    ModelRuntimeStrategy,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime

ModelOutput: TypeAlias = (
    PerceptionStateModel | VisionLanguageModelFrameEnvironment | str
)


@dataclass
class ModelStream:
    stop_event: threading.Event
    thread: threading.Thread


@dataclass(frozen=True)
class RegisteredModel:
    inference: Inference
    strategy: ModelRuntimeStrategy


@dataclass
class ModelRuntime:
    hardware_system: HardwareSystem
    camera_runtime: CameraRuntime
    model_outputs: dict[str, ModelOutput | None] = field(default_factory=dict)
    registered_models: dict[str, RegisteredModel] = field(default_factory=dict)
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
        registered_models: dict[str, RegisteredModel] = {}
        for model in self.hardware_system.models:
            if model.model_id in registered_models:
                raise ValueError(f"Duplicate model ID: {model.model_id}")
            inference = model.create_inference()
            strategy = MODEL_RUNTIME_STRATEGIES[type(inference)]
            if inference.model_output_keys.keys() != strategy.output_types.keys():
                raise ValueError(
                    f"Model output configuration does not match its strategy: "
                    f"{model.model_id}"
                )
            for key in inference.model_output_keys.values():
                if key in model_outputs:
                    raise ValueError(f"Duplicate model output key: {key}")
                model_outputs[key] = None
            registered_models[model.model_id] = RegisteredModel(
                inference=inference,
                strategy=strategy,
            )

        with self.lock:
            self.model_outputs = model_outputs
            self.registered_models = registered_models

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
        output_name: str,
    ) -> ModelOutput:
        with self.lock:
            registered_model = self.registered_models[model_id]
            output_type = registered_model.strategy.output_types[output_name]
            key = registered_model.inference.model_output_keys[output_name]
            model_output = self.model_outputs[key]
        if model_output is None:
            raise RuntimeError(f"Model output has not been produced yet: {key}")
        if not isinstance(model_output, output_type):
            raise TypeError(f"Model output has invalid type: {key}")
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

    def perform_object_detection(
        self,
        model_id: str,
    ) -> PerceptionStateModel:
        with self.lock:
            registered_model = self.registered_models[model_id]
        inference = registered_model.inference
        camera_id = inference.subscribed_camera.camera_id
        frame = self.camera_runtime.get_latest_frame(camera_id)
        return registered_model.strategy.perform(inference, frame)

    def locate_objects(
        self,
        model_id: str,
        frames: list[str],
        prompt: str,
    ) -> VisionLanguageModelFrameEnvironment:
        with self.lock:
            registered_model = self.registered_models[model_id]
        inference = registered_model.inference
        result = registered_model.strategy.locate_objects(
            inference,
            frames,
            prompt,
        )

        self.write_model_output(
            key=inference.model_output_keys["locate_object"],
            model_output=result,
        )
        return result

    def analyze_scene(
        self,
        model_id: str,
        frames: list[str],
        prompt: str,
    ) -> str:
        with self.lock:
            registered_model = self.registered_models[model_id]
        inference = registered_model.inference
        result = registered_model.strategy.analyze_scene(
            inference,
            frames,
            prompt,
        )

        self.write_model_output(
            key=inference.model_output_keys["scene_analysis"],
            model_output=result,
        )
        return result

    def turn_on_model_stream(
        self,
        model_id: str,
        prompt: str | None = None,
    ) -> None:
        with self.lock:
            registered_model = self.registered_models[model_id]
            stream = self.model_streams.get(model_id)
            if stream is not None and stream.thread.is_alive():
                raise RuntimeError(f"Model stream is already running: {model_id}")
            resolved_prompt = registered_model.strategy.resolve_stream_prompt(
                registered_model.inference,
                prompt,
            )
            prediction = partial(
                self.predict_latest_model,
                registered_model,
                resolved_prompt,
            )
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self.prediction_loop,
                args=(
                    model_id,
                    registered_model.inference.interval_seconds,
                    stop_event,
                    prediction,
                ),
                name=f"model.{model_id}",
                daemon=False,
            )
            self.model_streams[model_id] = ModelStream(stop_event, thread)
            try:
                thread.start()
            except RuntimeError:
                self.model_streams.pop(model_id)
                raise

    def predict_latest_model(
        self,
        registered_model: RegisteredModel,
        prompt: str | None,
    ) -> None:
        inference = registered_model.inference
        camera_id = inference.subscribed_camera.camera_id
        frame = self.camera_runtime.get_latest_frame(camera_id)
        result = registered_model.strategy.predict_stream(
            inference,
            frame,
            prompt,
        )
        self.write_model_output(
            key=inference.model_output_keys[
                registered_model.strategy.stream_output_name
            ],
            model_output=result,
        )

    def prediction_loop(
        self,
        model_id: str,
        interval_seconds: float,
        stop_event: threading.Event,
        prediction: Callable[[], None],
    ) -> None:
        try:
            while not stop_event.is_set():
                prediction()
                stop_event.wait(interval_seconds)
        finally:
            with self.lock:
                stream = self.model_streams[model_id]
                if stream.thread is not threading.current_thread():
                    raise RuntimeError(
                        f"Model stream ownership changed while running: {model_id}"
                    )
                self.model_streams.pop(model_id)

    def turn_off_model_stream(self, model_id: str) -> None:
        with self.lock:
            self.registered_models[model_id]
            stream = self.model_streams.get(model_id)
        if stream is None:
            raise RuntimeError(f"Model stream is not running: {model_id}")

        stream.stop_event.set()
        stream.thread.join(timeout=5.0)
        if stream.thread.is_alive():
            raise RuntimeError(f"Model stream did not stop: {model_id}")

    def turn_on_all_model_streams(self) -> None:
        with self.lock:
            registered_models = list(self.registered_models.items())

        started_model_ids: list[str] = []
        try:
            for model_id, registered_model in registered_models:
                prompt = registered_model.strategy.default_stream_prompt(
                    registered_model.inference,
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
