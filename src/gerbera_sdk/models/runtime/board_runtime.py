from dataclasses import dataclass, field
import threading
import time

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller

import serial

@dataclass
class SerialConnection:
    _conn: serial = None
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def connect(self, port: str, baud: int = 115200) -> None:
        self._conn = serial.Serial(port, baud, timeout=2)
        time.sleep(2)
        self._conn.reset_input_buffer()

    def write(self, command: str) -> None:
        with self._lock:
            self._conn.write(f"{command}\n".encode())
            self._conn.flush()

    def readline(self) -> bytes:
        return self._conn.readline()

    def destroy(self) -> None:
        with self._lock:
            if self._conn and self._conn.is_open:
                self._conn.close()


@dataclass
class BoardRuntime:
    hardware_system: HardwareSystem
    serial_pool: dict[str, SerialConnection] = field(default_factory=dict)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def start(self) -> None:
        try:
            with self._lock:
                for microcontroller in self.hardware_system.microcontrollers:
                    if microcontroller.id in self.serial_pool:
                        continue

                    connection = SerialConnection()
                    connection.connect(
                        port=microcontroller.port,
                        baud=microcontroller.baud_rate,
                    )
                    self.serial_pool[microcontroller.id] = connection
        except Exception as exc:
            self.close()
            raise RuntimeError("Could not start board runtime") from exc

    def get_serial_connection(
        self,
        microcontroller: Microcontroller,
    ) -> SerialConnection:
        with self._lock:
            connection = self.serial_pool.get(microcontroller.id)

        if connection is None:
            raise RuntimeError("Microcontroller does not exist")
        return connection

    def close(self) -> None:
        with self._lock:
            connections = list(self.serial_pool.items())

        first_error: Exception | None = None
        for microcontroller_id, serial_connection in connections:
            try:
                serial_connection.destroy()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                with self._lock:
                    if self.serial_pool.get(microcontroller_id) is serial_connection:
                        self.serial_pool.pop(microcontroller_id)

        if first_error is not None:
            raise RuntimeError("Could not stop board runtime") from first_error
