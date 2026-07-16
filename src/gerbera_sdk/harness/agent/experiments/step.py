from dataclasses import dataclass, field
import uuid

from action import Action

from enum import Enum

class StepStateEnum(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

@dataclass
class Step:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str # What or Why This Is Used
    action: Action # Event That Can Be Emitted (Tool Call Data Analysis or Something)
    status: StepStateEnum
    expected: str
    observed: str