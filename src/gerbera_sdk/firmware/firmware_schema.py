from dataclasses import dataclass, field
from gerbera_sdk.models.hardware.connection import Connection
from enum import Enum

GERBERA_PROTOCOL_VERSION = 1
GERBERA_HANDSHAKE_TARGET = "__gerbera__"
GERBERA_HANDSHAKE = "HANDSHAKE"
GERBERA_CHECK = "CHECK"
GERBERA_START = "START"
GERBERA_HEARTBEAT = "HEARTBEAT"
GERBERA_STOP = "STOP"
GERBERA_STATE_CHECKING = "CHECKING"
GERBERA_STATE_READY = "READY"
GERBERA_STATE_STOPPED = "STOPPED"
MAX_SERIAL_MESSAGE_BYTES = 1024

@dataclass(frozen=True)
class ParameterSpec:
    required: bool = True
    description: str = ""
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class CommandSpec:
    method: str
    params: dict[str, ParameterSpec] = field(default_factory=dict)
    description: str = ""


class PinMode(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class PinCapability(str, Enum):
    DIGITAL_INPUT = "digital_input"
    DIGITAL_OUTPUT = "digital_output"
    PWM_OUTPUT = "pwm_output"
    ANALOG_INPUT = "analog_input"
    INTERRUPT_INPUT = "interrupt_input"


class PinAssignmentMode(str, Enum):
    EXCLUSIVE = "exclusive"


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
