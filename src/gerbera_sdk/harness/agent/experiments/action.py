from dataclasses import dataclass, field
import uuid

@dataclass
class Method:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    target: str
    params: any
    