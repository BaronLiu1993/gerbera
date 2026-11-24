from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Connection:
    connection_id: str
    microcontroller_id: str
    
    component_type: ClassVar[str]
    supports_streaming: ClassVar[bool]
    include: ClassVar[str | None] = None
    library: ClassVar[str | None] = None


@dataclass
class DCMotor(Connection):
    in1: str
    in2: str
    enable: str
    component_type = "dcmotor"
    supports_streaming = False


@dataclass
class HCSR04(Connection):
    trig: str
    echo: str
    component_type = "hcsr04"
    supports_streaming = True


@dataclass
class HW201(Connection):
    out: str
    component_type = "hw201"
    supports_streaming = True


@dataclass
class KY033(Connection):
    out: str
    component_type = "ky033"
    supports_streaming = True


@dataclass
class LED(Connection):
    out: str
    component_type = "led"
    supports_streaming = False


@dataclass
class MG996R(Connection):
    signal: str
    component_type = "mg996r"
    supports_streaming = False
    include = "Servo.h"
    library = "Servo"


@dataclass
class SG90(Connection):
    signal: str
    component_type = "sg90"
    supports_streaming = False
    include = "Servo.h"
    library = "Servo"
