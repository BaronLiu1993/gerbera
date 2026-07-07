from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Pin:
    name: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Pin":
        return cls(
            name=str(payload["name"]),
            value=str(payload["value"]),
        )
