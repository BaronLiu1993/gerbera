from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.models.hardware.connection import Connection


@dataclass(kw_only=True)
class HCSR04(Connection):
    trig: str
    echo: str
    component_type: ClassVar[str] = "hcsr04"

    @property
    def pins(self) -> dict[str, str]:
        return {"trig": self.trig, "echo": self.echo}


@dataclass(kw_only=True)
class HW201(Connection):
    out: str
    component_type: ClassVar[str] = "hw201"

    @property
    def pins(self) -> dict[str, str]:
        return {"out": self.out}


@dataclass(kw_only=True)
class KY033(Connection):
    out: str
    component_type: ClassVar[str] = "ky033"

    @property
    def pins(self) -> dict[str, str]:
        return {"out": self.out}


@dataclass(kw_only=True)
class SG90(Connection):
    signal: str
    component_type: ClassVar[str] = "sg90"

    @property
    def pins(self) -> dict[str, str]:
        return {"signal": self.signal}


@dataclass(kw_only=True)
class MG996R(Connection):
    signal: str
    component_type: ClassVar[str] = "mg996r"

    @property
    def pins(self) -> dict[str, str]:
        return {"signal": self.signal}


@dataclass(kw_only=True)
class LED(Connection):
    out: str
    component_type: ClassVar[str] = "led"

    @property
    def pins(self) -> dict[str, str]:
        return {"out": self.out}


@dataclass(kw_only=True)
class DCMotor(Connection):
    in1: str
    in2: str
    enable: str
    component_type: ClassVar[str] = "dcmotor"

    @property
    def pins(self) -> dict[str, str]:
        return {"in1": self.in1, "in2": self.in2, "enable": self.enable}
