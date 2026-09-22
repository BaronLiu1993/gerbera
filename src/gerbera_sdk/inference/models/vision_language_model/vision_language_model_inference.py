from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Literal
import uuid

from pydantic import Field

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapters,
)
from gerbera_sdk.inference.model_types import VisionLanguageModelProviderEnum
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema, build_hashable_key

VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)

VISION_LANGUAGE_MODEL_VALID_NAME = {
    VisionLanguageModelProviderEnum.ANTHROPIC: ["opus-4.6"],
    VisionLanguageModelProviderEnum.OPENAI: [],
    VisionLanguageModelProviderEnum.GOOGLE: [],
}


class VisionLanguageModel(StrictSchema):
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1)
    model_provider: VisionLanguageModelProviderEnum
    user_prompt: str = Field(min_length=1)
    api_key: str
    model_name: str
    subscribed_camera: Camera
    timeout_seconds: float = 120.0
    max_tokens: int = 1024
    description: str = ""
    model_type: Literal["vision_language_model"] = "vision_language_model"
    model_operations: tuple[
        Literal["locate_object", "scene_analysis"], ...
    ] = (
        "locate_object",
        "scene_analysis",
    )
    interval_seconds: float = Field(default=5.0, gt=0)

    def model_output_keys(self) -> dict[str, dict[str, str]]:
        camera_id = self.subscribed_camera.camera_id
        return {
            operation: {
                camera_id: build_hashable_key(
                    self.model_id,
                    camera_id,
                    operation,
                )
            }
            for operation in self.model_operations
        }

    def create_inference(
        self,
        model_output_writer: Any,
        camera_runtime: Any,
    ) -> "VisionLanguageModelInference":
        if (
            self.model_name
            not in VISION_LANGUAGE_MODEL_VALID_NAME[self.model_provider]
        ):
            raise RuntimeError(
                f"Model Does Not Exist For Provider {self.model_provider}"
            )

        adapter = VISION_LANGUAGE_MODEL_REGISTRY[self.model_provider](
            api_key=self.api_key,
            model=self.model_name,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )
        return VisionLanguageModelInference(
            model=adapter,
            model_output_writer=model_output_writer,
            camera_runtime=camera_runtime,
            name=self.name,
            description=self.description,
            user_prompt=self.user_prompt,
            subscribed_camera=self.subscribed_camera,
            model_output_keys=self.model_output_keys(),
            interval_seconds=self.interval_seconds,
            model_id=self.model_id,
            model_type=self.model_type,
        )


@dataclass
class VisionLanguageModelInference:
    model: VisionLanguageModelAdapters
    name: str
    description: str
    user_prompt: str
    model_output_writer: Any = None
    camera_runtime: Any = None
    subscribed_camera: Camera | None = None
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "vision_language_model"
    model_output_keys: dict[str, dict[str, str]] = field(default_factory=dict)
    interval_seconds: float = 5.0
    _prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @property
    def subscribed_cameras(self) -> list[Camera]:
        if self.subscribed_camera is None:
            return []
        return [self.subscribed_camera]

    @property
    def system_prompt(self) -> str:
        base_prompt = VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH.read_text().strip()
        return "\n\n".join(
            [
                base_prompt,
                "## Configured model instructions",
                self.user_prompt.strip(),
            ]
        )

    def predict_latest_frames(self, prompt: str) -> None:
        if self.subscribed_camera is None or self.camera_runtime is None:
            raise RuntimeError("Vision language model stream has no camera runtime")
        if self.model_output_writer is None:
            raise RuntimeError("Vision language model stream has no output writer")
        camera_id = self.subscribed_camera.camera_id
        with self.camera_runtime.lock:
            frame = self.camera_runtime.latest_frames.get(camera_id)
        if frame is None:
            return

        model_output = self.predict(
            [frame.to_base64_string()],
            operation="locate_object",
            prompt=prompt,
        )
        self.model_output_writer.write_model_output(
            key=self.model_output_keys["locate_object"][camera_id],
            model_output=model_output,
        )

    def predict(
        self,
        base64_frames: list[str] | list[Frame],
        operation: Literal["locate_object", "scene_analysis"] = "locate_object",
        prompt: str | None = None,
    ) -> VisionLanguageModelFrameEnvironment | str:
        if not base64_frames:
            raise ValueError("At least one frame is required for inference")
        prompt = self.user_prompt if prompt is None else prompt

        with self._prediction_lock:
            model_input = [
                self.model.convert_to_valid_input(
                    frame.to_base64_string() if isinstance(frame, Frame) else frame
                )
                for frame in base64_frames
            ]
            if operation == "scene_analysis":
                return self.model.analyze_scene(
                    model_input=model_input,
                    system_prompt=self.system_prompt,
                    user_prompt=prompt,
                )

            if operation == "locate_object":
                output = self.model.predict(
                    model_input=model_input,
                    system_prompt=self.system_prompt,
                    user_prompt=prompt,
                    output_schema=(
                        VisionLanguageModelFrameEnvironment.model_json_schema()
                    ),
                )
                return VisionLanguageModelFrameEnvironment.model_validate(output)

        raise RuntimeError(f"Unsupported vision language operation: {operation}")
