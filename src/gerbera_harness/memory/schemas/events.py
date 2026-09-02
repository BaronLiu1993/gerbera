import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.base import HarnessSchema


class EventTypeEnum(str, Enum):
    SENSOR_READING = "sensor_reading"
    WORLD_STATE_UPDATED = "world_state_updated"
    PHYSICAL_CONFIGURATION_UPDATED = "physical_configuration_updated"

    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    OBSERVATION_CREATED = "observation_created"

    PLAN_CREATED = "plan_created"
    PLAN_INVALIDATED = "plan_invalidated"
    REPLAN_REQUESTED = "replan_requested"

    TOOL_CALL = "tool_call"


class SourceTypeEnum(str, Enum):
    MCP_TOOL = "mcp_tool"
    LOCAL_TOOL = "local_tool"
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class EventSchema(HarnessSchema):
    session_id: str
    event_type: EventTypeEnum
    source_name: str
    source_type: SourceTypeEnum
    payload: dict[str, Any]
    task_id: str
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class EventStateSchema(HarnessSchema):
    session_id: str
    events: list[EventSchema] = Field(default_factory=list)
