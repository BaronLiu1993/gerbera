from dataclasses import dataclass, field

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller

import time
import serial

@dataclass
class SerialConnection:
    _conn: serial = None

    def connect(self, port: str, baud: int = 115200) -> None:
        self._conn = serial.Serial(port, baud, timeout=2)
        time.sleep(2)
        self._conn.reset_input_buffer()

    def write(self, command: str) -> None:
        self._conn.write(f"{command}\n".encode())
        self._conn.flush()

    def readline(self) -> bytes:
        return self._conn.readline()

    def destroy(self) -> None:
        if self._conn and self._conn.is_open:
            self._conn.close()


@dataclass
class BoardRuntime:
    hardware_system: HardwareSystem
    serial_pool: dict[str, SerialConnection] = field(default_factory=dict)

    def start(self) -> None:
        try:
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
            raise RuntimeError(exc)

    def get_serial_connection(
        self,
        microcontroller: Microcontroller,
    ) -> SerialConnection:
        if microcontroller.id not in self.serial_pool:
            raise RuntimeError("Microcontroller does not exist")
        return self.serial_pool[microcontroller.id]

    def close(self) -> None:
        for serial_connection in self.serial_pool.values():
            serial_connection.destroy()

        self.serial_pool.clear()
