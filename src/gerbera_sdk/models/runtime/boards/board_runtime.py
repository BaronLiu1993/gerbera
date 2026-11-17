import threading
from dataclasses import dataclass, field

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.boards.board_transport import BoardTransport


@dataclass
class BoardRuntime:
    hardware_system: HardwareSystem
    transport_pool: dict[str, BoardTransport] = field(default_factory=dict, init=False)
    lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def start(self) -> None:
        with self.lock:
            try:
                for board in self.hardware_system.microcontrollers:
                    transport = BoardTransport(
                        port=board.runtime_transport.port,
                        baud_rate=board.baud_rate,
                    )
                    self.transport_pool[board.id] = transport
                    transport.connect()
            except BaseException:
                self.close()

    def close(self) -> None:
        with self.lock:
            for _, transport in tuple(self.transport_pool.items()):
                try:
                    transport.close()
                except Exception as error:
                    raise ValueError(error)

            

    def get_transport(self, microcontroller_id: str) -> BoardTransport:
        with self.lock:
            try:
                return self.transport_pool[microcontroller_id]
            except KeyError as error:
                raise RuntimeError(
                    f"Board is not connected: {microcontroller_id}"
                ) from error
