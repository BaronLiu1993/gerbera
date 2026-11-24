from dataclasses import dataclass, field
import threading
import serial

SERIAL_READ_TIMEOUT_SECONDS = 2.0

@dataclass
class BoardTransport:
    port: str
    baud_rate: int
    connection: serial.Serial | None = field(default=None, init=False, repr=False)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def connect(self) -> None:
        connection = serial.Serial(
            self.port,
            self.baud_rate,
            timeout=SERIAL_READ_TIMEOUT_SECONDS,
        )
        try:
            connection.reset_input_buffer()
        except BaseException as error:
            try:
                connection.close()
            except Exception as cleanup_error:
                error.add_note(f"Serial connection cleanup failed: {cleanup_error}")
            raise
        self.connection = connection

    def get_connection(self) -> serial.Serial:
        connection = self.connection
        if connection is None or not connection.is_open:
            raise RuntimeError("Board transport is not connected")
        return connection

    def write(self, command: str) -> None:
        with self.lock:
            connection = self.get_connection()
            connection.write(f"{command}\n".encode())
            connection.flush()

    def readline(self) -> bytes:
        return self.get_connection().readline()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
