from dataclasses import dataclass, field
import uuid
from enum import Enum

from gerbera_harness.agent.driver.step import Step

class MethodStateEnum(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

@dataclass
class Method:
    description: str
    name: str
    steps: list[Step]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    
