from gerbera_sdk.models.hardware.camera import Frame
from enum import Enum


class ModelTypeEnum(Enum):
    LOCAL = "local"
    CLOUD = "cloud"

ModelRegistry = {
    ModelTypeEnum.LOCAL: LocalModelAdapter,
    ModelTypeEnum.CLOUD: CloudModelAdapter
}

class ModelRegistry:
    @staticmethod
    def get_model_from_registry(model_type: ModelTypeEnum, model_provider: str):
        return ModelRegistry[model_type][model_provider]
