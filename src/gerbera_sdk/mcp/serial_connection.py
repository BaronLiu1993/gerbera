import time

import serial


class SerialConnection:
    def __init__(self):
        self._conn = None

    def connect(self, port: str, baud: int = 115200):
        self._conn = serial.Serial(port, baud, timeout=2)
        time.sleep(2)

    def send(self, command: str) -> str:
        self._conn.write(f"{command}\n".encode())
        return self._conn.readline().decode().strip()

    def destroy(self):
        if self._conn and self._conn.is_open:
            self._conn.close()
