import uuid
from enum import Enum
from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema

# will add more to compensate for all types of physical components
class PhysicalComponentEnum(str, Enum):
    SERVO_MOTOR = "servo_motor"
    DC_MOTOR = "dc_motor"
    IR_SENSOR = "ir_sensor"


class PhysicalEdgeSchema(HarnessSchema):
    source_id: str
    target_id: str
    description: str
    relationship_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class PhysicalNodeSchema(HarnessSchema):
    component_name: str
    description: str
    component_type: PhysicalComponentEnum
    capabilities: dict[str, Any]
    physical_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class PhysicalConfigurationStateSchema(HarnessSchema):
    session_id: str
    description: str
    physical_nodes: list[PhysicalNodeSchema] = Field(default_factory=list)
    physical_edges: list[PhysicalEdgeSchema] = Field(default_factory=list)
