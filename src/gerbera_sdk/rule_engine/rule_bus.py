from dataclasses import dataclass, field
from typing import Callable
import uuid

from gerbera_sdk.events.utils import EventKey


@dataclass
class RuleBus:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Keyed by the  event_type: str, microcontroller_id: str, event_name: str,
    rule_bus: dict[EventKey, Callable[dict[str, any], None]]

    
    def emit_evaluation_event(self, event_type, microcontroller_id, event_name):
        