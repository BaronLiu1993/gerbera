import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema


class WorldStateSchema(HarnessSchema):
    session_id: str
    environment_state: dict[str, Any] = Field(default_factory=dict)
    hardware_state: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    world_state_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
