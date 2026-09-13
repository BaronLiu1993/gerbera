from dataclasses import dataclass


@dataclass(frozen=True)
class Pin:
    name: str
    value: str
