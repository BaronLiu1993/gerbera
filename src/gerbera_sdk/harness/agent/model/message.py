from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

class EventTypeEnum(Enum):
    pass

class SourceTypeEnum(Enum):
    pass

@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventTypeEnum
    source_type: SourceTypeEnum
    payload: dict[str, any]
    timestamp: datetime
    session_id: str


    