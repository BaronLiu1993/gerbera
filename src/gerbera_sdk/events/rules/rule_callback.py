from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.events.rules.rule_condition import RuleValue


@dataclass
class RuleCallback:
    callback: Callable[[str, RuleValue], Awaitable[Any]]
    mcp_url: str
    val: RuleValue | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    async def define(self, val: RuleValue) -> Any:
        return await self.callback(self.mcp_url, val)

    async def __call__(self, val: RuleValue) -> Any:
        self.val = val
        return await self.define(val)
