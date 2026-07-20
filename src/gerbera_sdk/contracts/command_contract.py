from dataclasses import dataclass, field
from enum import Enum


class ParameterType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"


@dataclass(frozen=True)
class ParameterSpec:
    type: ParameterType = ParameterType.STRING
    required: bool = True
    enum: list[str] = field(default_factory=list)
    description: str = ""
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class CommandSpec:
    method: str
    params: dict[str, ParameterSpec] = field(default_factory=dict)
