from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import uuid


@dataclass
class RuleCallback:
    callback: Callable[[str, float], Awaitable[object]]
    mcp_url: str
    val: float | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    async def define(self, val: float) -> object:
        return await self.callback(self.mcp_url, val)

    async def __call__(self, val: float) -> object:
        self.val = val
        return await self.define(val)
