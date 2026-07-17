from dataclasses import dataclass, field
import uuid

from enum import Enum

class LoopStateEnum(Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"

@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: LoopStateEnum
    