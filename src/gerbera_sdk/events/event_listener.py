from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import logging
import threading
from typing import TYPE_CHECKING

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_schema import EventKey
from gerbera_sdk.latest_runtime import ConnectionState, HardwareRuntime
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec

if TYPE_CHECKING:
    from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime


logger = logging.getLogger(__name__)


@dataclass
class EventListener:
    board_runtime: "BoardRuntime"
    event_bus: EventBus
    hardware_runtime: HardwareRuntime
    on_event: Callable[[EventKey, Mapping[str, str]], None] | None = None
    thread_pool: dict[str, threading.Thread] = field(default_factory=dict, init=False)
    stop_event: threading.Event = field(default_factory=threading.Event, init=False)

    def create_listeners(self) -> None:
        if any(thread.is_alive() for thread in self.thread_pool.values()):
            raise RuntimeError("Event listeners are already running")

        self.thread_pool.clear()
        for board in self.board_runtime.hardware_system.microcontrollers:
            board_id = board.microcontroller_id
            self.thread_pool[board_id] = threading.Thread(
                target=self.listen_loop,
                args=(board_id,),
                daemon=False,
                name=f"serial-listener-{board_id}",
            )

    def start_listeners(self) -> None:
        if any(thread.ident is not None for thread in self.thread_pool.values()):
            raise RuntimeError("Create new listeners before starting them again")

        self.stop_event.clear()
        try:
            for thread in self.thread_pool.values():
                thread.start()
        except BaseException:
            self.stop_listeners()
            raise

    def stop_listeners(self, timeout: float = 2.0) -> None:
        self.stop_event.set()
        for thread in self.thread_pool.values():
            if thread.ident is not None:
                thread.join(timeout=timeout)

    def listen_loop(self, microcontroller_id: str) -> None:
        transport = self.board_runtime.get_transport(microcontroller_id)
        while not self.stop_event.is_set():
            try:
                line = transport.readline()
                if line:
                    self.process_message(microcontroller_id, line)
            except (RuntimeError, ValueError):
                continue

    def process_message(self, microcontroller_id: str, line: bytes | str) -> None:
        message = SerialMessageCodec.decode(line)
        event = self.event_bus.get_event(message.message_type, microcontroller_id, message.target)
        if len(message.fields) != 1:
            raise ValueError("Hardware messages must contain exactly one field")

        name, value = next(iter(message.fields.items()))
        if message.message_type == "MCP" and name == "error":
            logger.warning(
                "Board %s connection %s returned %s", microcontroller_id, message.target, value
            )
            return
        if name not in event.payload_fields:
            raise ValueError(f"Unexpected hardware field: {name}")

        state_key = (microcontroller_id, message.target, name)
        self.hardware_runtime.update_state(state_key, ConnectionState(value, event.payload_fields[name]))
        event.stream_data(message.fields)
        if self.on_event is not None:
            self.on_event(event.event_key, message.fields)
