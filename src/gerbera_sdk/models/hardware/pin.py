from dataclasses import dataclass
from enum import Enum
from typing import Any


class PinName(str, Enum):
    OUT = "out"
    SIGNAL = "signal"
    TX = "tx"
    RX = "rx"
    SDA = "sda"
    SCL = "scl"


@dataclass(frozen=True)
class Pin:
    name: PinName
    value: str
