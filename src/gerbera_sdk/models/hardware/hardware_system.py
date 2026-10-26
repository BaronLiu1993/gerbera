from dataclasses import field
from typing import Annotated
import uuid

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

from gerbera_sdk.inference import Model
from gerbera_sdk.models.hardware.camera import Camera
from gerbera_sdk.firmware.boards import BOARD_REGISTRY
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.hardware.movement_system import MovementSystem

@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, arbitrary_types_allowed=True))
class HardwareSystem:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    description: str = ""
    movement_systems: list[MovementSystem] = field(default_factory=list)
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    cameras: list[Camera] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)
    id: Annotated[str, Field(min_length=1, pattern=r"\S")] = field(default_factory=lambda: str(uuid.uuid4()))

    def get_required_microcontroller_libraries(self) -> list[str]:
        libraries: list[str] = []
        normalized_library_names: set[str] = set()

        for microcontroller in self.microcontrollers:
            board_definition = BOARD_REGISTRY.get_definition(
                microcontroller.fqbn
            )

            for library in board_definition.libraries:
                normalized_library = library.strip().lower()
                if normalized_library not in normalized_library_names:
                    libraries.append(library)
                    normalized_library_names.add(normalized_library)
        return libraries
