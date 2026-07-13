import time

import serial


class SerialConnection:
    def __init__(self):
        self._conn = None

    def connect(self, port: str, baud: int = 115200):
        self._conn = serial.Serial(port, baud, timeout=2)
        time.sleep(2)
        self._conn.reset_input_buffer()

    def send(self, command: str) -> str:
        self.write(command)
        return ""

    def write(self, command: str) -> None:
        self._conn.write(f"{command}\n".encode())
        self._conn.flush()

    def readline(self) -> bytes:
        return self._conn.readline()

    def close(self):
        self.destroy()

    def destroy(self):
        if self._conn and self._conn.is_open:
            self._conn.close()
