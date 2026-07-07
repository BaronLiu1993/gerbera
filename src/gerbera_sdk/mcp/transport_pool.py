from gerbera_sdk.hardware.hardware_system import HardwareSystem
from gerbera_sdk.transport.serial_connection import SerialConnection


class SerialTransportPool:
    def __init__(self, hardware_system: HardwareSystem):
        self.hardware_system = hardware_system
        self._connections: dict[str, SerialConnection] = {}

    def get_connection(self, microcontroller_id: str) -> SerialConnection:
        if microcontroller_id in self._connections:
            return self._connections[microcontroller_id]

        microcontroller = self.hardware_system.get_microcontroller(microcontroller_id)

        serial_connection = SerialConnection()
        serial_connection.connect(
            port=microcontroller.port,
            baud=microcontroller.baud_rate,
        )
        self._connections[microcontroller_id] = serial_connection
        return serial_connection

    def execute(self, microcontroller_id: str, connection_name: str) -> dict:
        prepared_command = self.hardware_system.prepare_command(
            microcontroller_id=microcontroller_id,
            connection_name=connection_name,
        )
        serial_connection = self.get_connection(microcontroller_id)
        response = serial_connection.send(str(prepared_command["command"]))
        return self.hardware_system.parse_response(response)

    def close(self, microcontroller_id: str) -> None:
        serial_connection = self._connections.pop(microcontroller_id, None)
        if serial_connection is not None:
            serial_connection.destroy()

    def close_all(self) -> None:
        for microcontroller_id in list(self._connections.keys()):
            self.close(microcontroller_id)
