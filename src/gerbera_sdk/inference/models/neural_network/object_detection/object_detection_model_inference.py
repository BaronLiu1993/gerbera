from dataclasses import dataclass
from pathlib import Path

from gerbera_sdk.inference.frame import (
    Frame,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.inference.inference import ModelTypes
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    VisionLanguageModelAdapters,
)


VISION_LANGUAGE_MODEL_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "vision_language_model.md"
)


@dataclass
class ObjectDetectionModelInference:
    model: VisionLanguageModelAdapters
    name: str
    description: str
    model_type: ModelTypes = ModelTypes.OBJECT_DETECTION
    interval_seconds: float = 5.0

