from dataclasses import dataclass, field
from pathlib import Path

from pydantic import Field, InstanceOf
import threading
import uuid

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.model_output_store import ModelOutputStore
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapters,
)
from gerbera_sdk.inference.model_types import (
    VisionLanguageModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema

VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)

VISION_LANGUAGE_MODEL_VALID_NAME = {
    VisionLanguageModelProviderEnum.ANTHROPIC: ["opus-4.6"],
    VisionLanguageModelProviderEnum.OPENAI: [],
    VisionLanguageModelProviderEnum.GOOGLE: [],
}


class VisionLanguageModel(StrictSchema):
    # We need these
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1)
    model_provider: VisionLanguageModelProviderEnum

    # Pass To the Model Itself
    user_prompt: str = Field(min_length=1)
    api_key: str
    model_name: str
    timeout_seconds: float = 120.0
    max_tokens: int = 1024

    subscribed_cameras: list[InstanceOf[Camera]] = Field(min_length=1)

    # optional
    description: str = ""
    interval_seconds: float = Field(default=5.0, gt=0)

    def create_inference(
        self,
        model_output_store: ModelOutputStore,
    ) -> "VisionLanguageModelInference":
        if self.model_name not in VISION_LANGUAGE_MODEL_VALID_NAME[self.model_provider]:
            raise RuntimeError(
                f"Model Does Not Exist For Provider {self.model_provider}"
            )

        vision_language_model_object = VISION_LANGUAGE_MODEL_REGISTRY[
            self.model_provider
        ](
            api_key=self.api_key,
            model=self.model_name,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )

        return VisionLanguageModelInference(
            model_session=VLMSession(
                model=vision_language_model_object,
                model_output_store=model_output_store,
            ),
            name=self.name,
            description=self.description,
            user_prompt=self.user_prompt,
            subscribed_cameras=self.subscribed_cameras,
            interval_seconds=self.interval_seconds,
            model_id=self.model_id,
        )


@dataclass
class VLMSession:
    model: VisionLanguageModelAdapters
    model_output_store: ModelOutputStore
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None


@dataclass
class VisionLanguageModelInference:
    model_session: VLMSession
    name: str
    description: str
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_prompt: str = Field(min_length=1)
    subscribed_cameras: list[Camera] = field(default_factory=list)
    interval_seconds: float = 5.0
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @property
    def is_running(self) -> bool:
        with self._lock:
            thread = self.model_session._thread
            stop_event = self.model_session._stop_event
            if (thread is None) != (stop_event is None):
                raise RuntimeError("Vision language model thread state is invalid")
            return thread is not None

    @property
    def system_prompt(self) -> str:
        return VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH.read_text().strip()

    def turn_on_prediction_loop(self) -> None:
        with self._lock:
            if (
                self.model_session._thread is not None
                or self.model_session._stop_event is not None
            ):
                raise RuntimeError(
                    f"Vision language model is already running: {self.name}"
                )

            stop_event = threading.Event()
            thread = threading.Thread(
                target=self.prediction_loop,
                name=f"vision-language-model-{self.name}",
                daemon=False,
            )
            self.model_session._stop_event = stop_event
            self.model_session._thread = thread

            try:
                thread.start()
            except RuntimeError as exc:
                self.model_session._stop_event = None
                self.model_session._thread = None
                raise RuntimeError(
                    f"Could Not Start Vision Language Model Thread {self.name}"
                ) from exc

    def turn_off_prediction_loop(self) -> None:
        with self._lock:
            stop_event = self.model_session._stop_event
            thread = self.model_session._thread
            if stop_event is None or thread is None:
                raise RuntimeError(
                    f"Vision language model is not running: {self.name}"
                )

            stop_event.set()
            thread.join(timeout=5.0)
            if thread.is_alive():
                raise RuntimeError(
                    f"Vision language model thread did not stop: {self.name}"
                )

            self.model_session._stop_event = None
            self.model_session._thread = None

    def prediction_loop(self) -> None:
        stop_event = self.model_session._stop_event
        if stop_event is None:
            raise RuntimeError(
                "Vision language model prediction loop has no stop event"
            )

        while not stop_event.is_set():
            cameras: list[Camera] = []
            frames: list[Frame] = []
            for camera in self.subscribed_cameras:
                frame = camera.latest_frame
                if frame is not None:
                    cameras.append(camera)
                    frames.append(frame)

            if cameras:
                model_output = self.predict(
                    [frame.to_base64_string() for frame in frames]
                )

                for camera in cameras:
                    self.model_session.model_output_store.write_model_output(
                        camera_id=camera.camera_id,
                        model_id=self.model_id,
                        model_output=model_output,
                    )

            stop_event.wait(self.interval_seconds)

    # Single predict function
    def predict(
        self,
        base64_frames: list[str],
    ) -> VisionLanguageModelFrameEnvironment:
        if not base64_frames:
            raise ValueError("At least one frame is required for inference")

        with self._prediction_lock:
            valid_frame_input = [
                self.model_session.model.convert_to_valid_input(frame)
                for frame in base64_frames
            ]

            output = self.model_session.model.predict(
                model_input=valid_frame_input,
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt,
                output_schema=(
                    VisionLanguageModelFrameEnvironment.model_json_schema()
                ),
            )
            return VisionLanguageModelFrameEnvironment.model_validate(output)
