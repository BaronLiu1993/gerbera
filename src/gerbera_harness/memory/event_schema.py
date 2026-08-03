import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventTypeEnum(str, Enum):
    ACTION_SELECTED = "action_selected"
    TOOL_CALL = "tool_call"
    WORLD_STATE_UPDATED = "world_state_updated"
    TASK_STATUS_CHANGED = "task_status_changed"
    STATE_TRANSITION = "state_transition"
    SUBLOOP_COMPLETED = "subloop_completed"
    SUBLOOP_BLOCKED = "subloop_blocked"


class SourceTypeEnum(str, Enum):
    USER = "user"
    MODEL = "model"
    RUNTIME = "runtime"
    MCP_TOOL = "mcp_tool"


@dataclass
class EventSchema:
    event_type: EventTypeEnum
    source_type: SourceTypeEnum
    payload: dict[str, Any]
    session_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
