from dataclasses import dataclass

from gerbera_sdk.inference import Model
from gerbera_sdk.inference.model_types import ModelCatalogType
from gerbera_sdk.models.hardware.camera import Camera


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    name: str
    description: str
    model_type: ModelCatalogType
    subscribed_camera: Camera
    model_output_keys: dict[str, str]

    @classmethod
    def from_declaration(cls, model: Model) -> "ModelDescriptor":
        return cls(
            model_id=model.model_id, name=model.name, description=model.description,
            model_type=model.model_type, subscribed_camera=model.subscribed_camera,
            model_output_keys=model.model_output_keys(),
        )
