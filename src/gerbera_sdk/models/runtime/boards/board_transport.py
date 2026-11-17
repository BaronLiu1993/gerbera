from dataclasses import dataclass, field
import threading
import time

import serial

SERIAL_READ_TIMEOUT_SECONDS = 2.0

@dataclass
class BoardTransport:
    port: str
    baud_rate: int
    connection: serial.Serial = field(default=None, init=False, repr=False)
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
        self.connection.reset_input_buffer()

    def write(self, command: str) -> None:
        with self.lock:
            connection = self.get_connection()
            connection.write(f"{command}\n".encode())
            connection.flush()

    def readline(self) -> bytes:
        return self.get_connection().readline()

    def close(self) -> None:
        with self.lock:
            if self.connection is not None and self.connection.is_open:
                self.connection.close()

    def get_connection(self) -> serial.Serial:
        if self.connection is None or not self.connection.is_open:
            raise RuntimeError("Board transport is not connected")
        return self.connection

