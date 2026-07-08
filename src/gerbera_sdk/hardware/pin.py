from dataclasses import dataclass
from enum import Enum
from typing import Any


class PinName(str, Enum):
    OUT = "out"
    TX = "tx"
    RX = "rx"
    SDA = "sda"
    SCL = "scl"


@dataclass(frozen=True)
class Pin:
    name: PinName
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Pin":
        return cls(
            name=PinName(str(payload["name"]).strip().lower()),
            value=str(payload["value"]),
        )
