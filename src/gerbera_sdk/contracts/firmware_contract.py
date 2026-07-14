from dataclasses import dataclass
from enum import Enum


class PinMode(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


@dataclass(frozen=True)
class PinModeSpec:
    pin: str
    mode: PinMode


@dataclass(frozen=True)
class LibrarySpec:
    include: str
    install: str

@dataclass(frozen=True)
class ColumnType(str, Enum):
    INTEGER = "INTEGER"
    FLOAT = "DOUBLE PRECISION"
    TIMESTAMP = "TIMESTAMP"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"


@dataclass(frozen=True)
class ColumnSpec:
    type: ColumnType
    idx: bool = False
    primary_key: bool = False
    nullable: bool = True
    default: str | None = None
    sql_suffix: str | None = None
