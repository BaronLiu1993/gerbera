from dataclasses import dataclass, field

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime


@dataclass
class EventRuntime:
    hardware_system: HardwareSystem
    board_runtime: BoardRuntime
    event_bus: EventBus = field(default_factory=EventBus)
    event_listener: EventListener = field(default=None, init=False)

    def register_event_bus(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                connection.event_bus = self.event_bus

    def start_event_listener(self) -> None:
        if self.event_listener is not None:
            return

        self.event_listener = EventListener(
            hardware_system=self.hardware_system,
            _serial_pool=self.board_runtime.serial_pool,
            _threads={},
            _event_bus=self.event_bus,
        )
        self.event_listener.create_listeners()

    def stop_event_listener(self) -> None:
        if self.event_listener is None:
            return

        self.event_listener.stop_listeners()
        self.event_listener = None
