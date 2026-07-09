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
