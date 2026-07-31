from enum import Enum

from gerbera_sdk.inference.cloud_model_adapter import (
    CloudModelAdapter,
    CloudModelAdapterRegistry,
    ModelProviderEnum,
)
from gerbera_sdk.inference.local_model_adapter import LocalModelAdapter


class ModelTypeEnum(Enum):
    LOCAL = "local"
    CLOUD = "cloud"


_MODEL_REGISTRY = {
    ModelTypeEnum.LOCAL: LocalModelAdapter,
    ModelTypeEnum.CLOUD: CloudModelAdapterRegistry,
}


class ModelRegistry:
    @staticmethod
    def get_model_from_registry(
        model_type: ModelTypeEnum,
        model_provider: str,
    ) -> type[LocalModelAdapter] | type[CloudModelAdapter]:
        registered_model = _MODEL_REGISTRY[model_type]
        if registered_model is LocalModelAdapter:
            return registered_model

        provider = ModelProviderEnum(model_provider)
        return registered_model[provider]
