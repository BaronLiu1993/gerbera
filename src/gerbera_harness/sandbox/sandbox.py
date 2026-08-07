from abc import ABC, abstractmethod
from dataclasses import field, dataclass
import uuid
import subprocess


@dataclass
class Sandbox:
    run_id: str = field(default_factory=uuid.uuid4()) # subagent id that was used
    session_id: str # Pass in from the session
    
    # Bubble Wrap
    def run(self, command: list[str], max_time: float = 30.0) -> None:
        raise NotImplementedError 
