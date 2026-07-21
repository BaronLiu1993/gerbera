from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class EventTypeEnum(str, Enum):
    STATE_RESPONSE = "state_response"


class SourceTypeEnum(str, Enum):
    MODEL = "model"


@dataclass
class Event:
    event_type: EventTypeEnum
    source_type: SourceTypeEnum
    payload: dict[str, Any]
    session_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
