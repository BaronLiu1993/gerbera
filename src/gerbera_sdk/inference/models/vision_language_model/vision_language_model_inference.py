from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
import threading
from typing import ClassVar, Literal, Sequence
import uuid

from pydantic import Field

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VISION_LANGUAGE_MODEL_REGISTRY,
    VisionLanguageModelAdapter,
)
from gerbera_sdk.inference.model_types import (
    VisionLanguageModelProviderEnum,
    build_model_output_keys,
)
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.utils import StrictSchema

VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)


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
    model_operations: ClassVar[tuple[
        Literal["locate_object", "scene_analysis"], ...
    ]] = (
        "locate_object",
        "scene_analysis",
    )
    interval_seconds: float = Field(default=5.0, gt=0)

    def model_output_keys(self) -> dict[str, str]:
        return build_model_output_keys(
            self.model_id,
            self.subscribed_camera.camera_id,
            self.model_operations,
        )

    def create_inference(self) -> "VisionLanguageModelInference":
        adapter = VISION_LANGUAGE_MODEL_REGISTRY[self.model_provider](
            api_key=self.api_key,
            model=self.model_name,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )
        return VisionLanguageModelInference(
            model=adapter,
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
    model: VisionLanguageModelAdapter
    name: str
    description: str
    user_prompt: str
    subscribed_camera: Camera
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: str = "vision_language_model"
    model_output_keys: dict[str, str] = field(default_factory=dict)
    interval_seconds: float = 5.0
    _prediction_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    @cached_property
    def system_prompt(self) -> str:
        base_prompt = VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH.read_text().strip()
        return "\n\n".join(
            [
                base_prompt,
                "## Configured model instructions",
                self.user_prompt.strip(),
            ]
        )

    def predict(
        self,
        frames: Sequence[str | Frame],
        prompt: str,
        operation: Literal["locate_object", "scene_analysis"] = "locate_object",
    ) -> VisionLanguageModelFrameEnvironment | str:
        if not frames:
            raise ValueError("At least one frame is required for inference")

        with self._prediction_lock:
            model_input = [
                self.model.convert_to_valid_input(
                    frame.to_base64_string() if isinstance(frame, Frame) else frame
                )
                for frame in frames
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
