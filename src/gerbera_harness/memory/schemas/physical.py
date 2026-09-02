from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema


class PhysicalConfigurationStateSchema(HarnessSchema):
    session_id: str
    hardware_state_by_name: dict[str, Any] = Field(default_factory=dict)
    joint_state_by_movement_system: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
