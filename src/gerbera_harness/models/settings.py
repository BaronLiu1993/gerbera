from dataclasses import dataclass, field
from typing import Literal


TokenLimitParameter = Literal["max_tokens", "max_completion_tokens"]


@dataclass(frozen=True)
class ModelConnectionSettings:
    model: str
    endpoint: str
    timeout_seconds: float = 120
    api_key: str | None = field(default=None, repr=False, kw_only=True)
    maximum_tokens: int | None = field(default=None, kw_only=True)
