from enum import Enum


class VisionLanguageModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"

class ObjectDetectionModelProviderEnum(Enum):
    YOLOV5 = "yolov5"
    YOLOV8 = "yolov8"
