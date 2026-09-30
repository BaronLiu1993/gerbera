from dataclasses import dataclass, field
from typing import Protocol
import threading
import time

import serial

from gerbera_sdk.firmware.firmware_schema import BoardTransportKind
from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard

SERIAL_READ_TIMEOUT_SECONDS = 2.0
USB_BOOT_WAIT_SECONDS = 2.0


class BoardTransport(Protocol):
    def connect(self) -> None: ...

    def write(self, command: str) -> None: ...

    def readline(self) -> bytes: ...

    def cancel_read(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class SerialBoardTransport:
    port: str
    baud_rate: int
    boot_wait_seconds: float
    connection: serial.Serial | None = None
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def connect(self) -> None:
        self.connection = serial.Serial(
            self.port,
            self.baud_rate,
            timeout=SERIAL_READ_TIMEOUT_SECONDS,
        )
        if self.boot_wait_seconds:
            time.sleep(self.boot_wait_seconds)
        self.connection.reset_input_buffer()

    def write(self, command: str) -> None:
        with self.lock:
            connection = self.require_connection()
            connection.write(f"{command}\n".encode())
            connection.flush()

    def readline(self) -> bytes:
        return self.require_connection().readline()

    def cancel_read(self) -> None:
        cancel_read = getattr(self.require_connection(), "cancel_read", None)
        if cancel_read is not None:
            cancel_read()

    def close(self) -> None:
        with self.lock:
            if self.connection is not None and self.connection.is_open:
                self.connection.close()

    def require_connection(self) -> serial.Serial:
        if self.connection is None or not self.connection.is_open:
            raise RuntimeError("Board transport is not connected")
        return self.connection


class BoardTransportFactory:
    @staticmethod
    def create(board: ResolvedBoard) -> BoardTransport:
        transport = board.active_runtime_transport
        boot_wait_seconds = (
            USB_BOOT_WAIT_SECONDS
            if transport.kind == BoardTransportKind.USB_SERIAL
            else 0.0
        )
        return SerialBoardTransport(
            port=transport.port,
            baud_rate=board.baud_rate,
            boot_wait_seconds=boot_wait_seconds,
        )
