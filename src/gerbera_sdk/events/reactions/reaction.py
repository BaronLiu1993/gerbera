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
    latest_value: float | None = None
    trigger_mode: ReactionTriggerModeEnum = ReactionTriggerModeEnum.REPEAT
    has_triggered: bool = field(default=False, init=False, repr=False)
    trigger_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def can_trigger(self) -> bool:
        if self.trigger_mode == ReactionTriggerModeEnum.REPEAT:
            return True

        with self.trigger_lock:
            if self.has_triggered:
                return False

            self.has_triggered = True
            return True

    async def perform_work(self) -> object | None:
        if self.latest_value is None:
            return

        if not self.condition.evaluate_condition(self.latest_value):
            return

        if not self.can_trigger():
            return

        return await self.callback(val=self.latest_value)
