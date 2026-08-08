from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.connection import Connection


class PinMode(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

class ColumnType(str, Enum):
    INTEGER = "INTEGER"
    FLOAT = "DOUBLE PRECISION"
    TIMESTAMP = "TIMESTAMP"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"


@dataclass(frozen=True)
class PinModeSpec:
    pin: str
    mode: PinMode


@dataclass(frozen=True)
class LibrarySpec:
    include: str
    install: str


@dataclass(frozen=True)
class ColumnSpec:
    type: ColumnType
    idx: bool = False
    primary_key: bool = False
    nullable: bool = True
    default: str | None = None
    sql_suffix: str | None = None


@dataclass(frozen=True)
class StreamContract:
    event_name: str
    table_name: str
    schema: dict[str, ColumnSpec]
    connection: "Connection"
