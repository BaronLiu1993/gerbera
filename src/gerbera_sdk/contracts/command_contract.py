from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParameterSpec:
    required: bool = True
    description: str = ""
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class CommandSpec:
    method: str
    params: dict[str, ParameterSpec] = field(default_factory=dict)
    description: str = ""
