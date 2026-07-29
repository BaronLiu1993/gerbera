from dataclasses import dataclass, field
import uuid


@dataclass
class Action:
    type: str
    target: str
    params: dict[str, dict[str, str]]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

