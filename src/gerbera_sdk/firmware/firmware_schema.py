from dataclasses import dataclass
from enum import Enum

MAX_SERIAL_MESSAGE_BYTES = 1024


class BoardTransportKind(str, Enum):
    USB_SERIAL = "usb_serial"
    BLUETOOTH_CLASSIC = "bluetooth_classic"


class PinMode(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class PinCapability(str, Enum):
    DIGITAL_INPUT = "digital_input"
    DIGITAL_OUTPUT = "digital_output"
    PWM_OUTPUT = "pwm_output"
    ANALOG_INPUT = "analog_input"
    INTERRUPT_INPUT = "interrupt_input"

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
