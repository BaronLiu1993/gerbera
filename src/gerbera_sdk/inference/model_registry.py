from enum import Enum

from gerbera_sdk.inference.models.vision_language_model.vision_language_model_adapter import (
    ModelProviderEnum,
    VisionLanguageModelAdapter,
    VisionLanguageModelAdapterRegistry,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_adapter import (
    ObjectDetectionAdapter,
)


class ModelTypeEnum(Enum):
    LOCAL = "local"
    CLOUD = "cloud"


_MODEL_REGISTRY = {
    ModelTypeEnum.LOCAL: ObjectDetectionAdapter,
    ModelTypeEnum.CLOUD: VisionLanguageModelAdapterRegistry,
}


class ModelRegistry:
    @staticmethod
    def get_model_from_registry(
        model_type: ModelTypeEnum,
        model_provider: str,
    ) -> type[ObjectDetectionAdapter] | type[VisionLanguageModelAdapter]:
        registered_model = _MODEL_REGISTRY[model_type]
        if registered_model is ObjectDetectionAdapter:
            return registered_model

        provider = ModelProviderEnum(model_provider)
        return registered_model[provider]
