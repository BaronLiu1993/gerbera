from dataclasses import dataclass

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.runtime.movement_runtime import MovementRuntime


@dataclass
class HardwareGateway:
    movement_runtime: MovementRuntime