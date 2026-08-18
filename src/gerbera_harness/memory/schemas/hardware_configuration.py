import uuid
from enum import Enum
from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema

# will add more to compensate for all types of hardware
class HardwareComponentEnum(str, Enum):
    SERVO_MOTOR = "servo_motor"
    DC_MOTOR = "dc_motor"
    IR_SENSOR = "ir_sensor"


class HardwareEdgeSchema(HarnessSchema):
    source_id: str
    target_id: str
    description: str
    relationship_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class HardwareNodeSchema(HarnessSchema):
    component_name: str
    description: str
    component_type: HardwareComponentEnum
    capabilities: dict[str, Any]
    hardware_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class HardwareConfigurationStateSchema(HarnessSchema):
    session_id: str
    description: str
    hardware_nodes: list[HardwareNodeSchema] = Field(default_factory=list)
    hardware_edges: list[HardwareEdgeSchema] = Field(default_factory=list)
