from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import uuid

from gerbera_sdk.events.reactions.reaction_callback import ReactionCallback
from gerbera_sdk.events.reactions.reaction_condition import ReactionCondition


class ReactionTriggerModeEnum(str, Enum):
    ONCE = "once"
    REPEAT = "repeat"


@dataclass
class Reaction:
    condition: ReactionCondition
    callback: ReactionCallback
    trigger_mode: ReactionTriggerModeEnum = ReactionTriggerModeEnum.REPEAT
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _has_triggered: bool = field(default=False, init=False, repr=False)
    _trigger_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def has_triggered(self) -> bool:
        with self._trigger_lock:
            return self._has_triggered

    def claim_trigger(self) -> bool:
        if self.trigger_mode == ReactionTriggerModeEnum.REPEAT:
            return True

        with self._trigger_lock:
            if self._has_triggered:
                return False

            self._has_triggered = True
            return True
