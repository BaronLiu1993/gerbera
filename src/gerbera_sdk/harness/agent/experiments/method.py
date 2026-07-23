from dataclasses import dataclass, field
import uuid
from enum import Enum

from gerbera_sdk.harness.agent.experiments.step import Step

class MethodStateEnum(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

@dataclass
class Method:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    name: str
    steps: list[Step]
    
