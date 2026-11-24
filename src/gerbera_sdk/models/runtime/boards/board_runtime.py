from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gerbera_sdk.models.runtime.boards.board_transport import BoardTransport
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessage, SerialMessageCodec

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.connection import Connection
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class BoardRuntime:
    hardware_system: "HardwareSystem"
    transport_pool: dict[str, BoardTransport] = field(default_factory=dict, init=False)

    def start(self) -> None:
        if self.transport_pool:
            return

        try:
            for board in self.hardware_system.microcontrollers:
                transport = BoardTransport(port=board.upload_port, baud_rate=board.baud_rate)
                transport.connect()
                self.transport_pool[board.microcontroller_id] = transport
        except BaseException as error:
            try:
                self.close()
            except Exception as cleanup_error:
                error.add_note(f"Board startup cleanup failed: {cleanup_error}")
            raise

    def close(self) -> None:
        with ExitStack() as cleanup:
            for transport in self.transport_pool.values():
                cleanup.callback(transport.close)
            self.transport_pool.clear()

    def get_transport(self, microcontroller_id: str) -> BoardTransport:
        try:
            return self.transport_pool[microcontroller_id]
        except KeyError as error:
            raise RuntimeError(f"Board is not connected: {microcontroller_id}") from error

    def write_connection(self, connection: "Connection", fields: Mapping[str, int]) -> None:
        message = SerialMessage(
            message_type="WRITE",
            target=connection.connection_id,
            fields={name: str(value) for name, value in fields.items()},
        )
        line = SerialMessageCodec.encode(message)
        self.get_transport(connection.microcontroller_id).write(line)
