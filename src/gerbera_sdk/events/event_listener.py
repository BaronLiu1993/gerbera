from collections.abc import Mapping
import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import threading
import time
from typing import Callable

from serial import SerialException

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.runtime.board_transport import BoardTransport
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.hardware_runtime import (
    ConnectionState,
    HardwareRuntime,
)
from gerbera_sdk.models.runtime.serial_protocol import SerialMessageCodec

RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF_SECONDS = 0.25


@dataclass
class EventListener:
    hardware_plan: HardwarePlan
    transport_pool: Mapping[str, BoardTransport]

    event_bus: EventBus
    reaction_bus: ReactionBus
    hardware_runtime: HardwareRuntime
    reconnect_board: Callable[[str], None] | None = None

    reaction_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gerbera-reaction-callback",
        )
    )
    threads: dict[str, threading.Thread] = field(
        default_factory=dict
    )
    stop_event: threading.Event = field(default_factory=threading.Event)
    lifecycle_lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def create_listeners(self) -> None:
        with self.lifecycle_lock:
            self.stop_event.clear()
            for board in self.hardware_plan.boards:
                microcontroller_id = board.microcontroller_id

                thread = threading.Thread(
                    target=self.listen_loop,
                    args=(microcontroller_id,),
                    daemon=False,
                    name=f"serial-listener-{microcontroller_id}",
                )

                self.threads[microcontroller_id] = thread
                thread.start()

    def stop_listeners(self, timeout: float = 2.0) -> None:
        with self.lifecycle_lock:
            self.stop_event.set()
            threads = list(self.threads.items())

        for transport in list(self.transport_pool.values()):
            transport.cancel_read()

        alive_threads = {}
        for microcontroller_id, thread in threads:
            thread.join(timeout=timeout)
            if thread.is_alive():
                alive_threads[microcontroller_id] = thread

        with self.lifecycle_lock:
            self.threads = alive_threads

        self.reaction_executor.shutdown(wait=True, cancel_futures=True)

        if alive_threads:
            names = ", ".join(thread.name for thread in alive_threads.values())
            raise RuntimeError(f"Event listener threads did not stop: {names}")

    def listen_loop(self, microcontroller_id: str) -> None:
        while not self.stop_event.is_set():
            transport = self.transport_pool[microcontroller_id]
            try:
                line = transport.readline()
            except (OSError, SerialException):
                if self.stop_event.is_set():
                    return
                self.reconnect(microcontroller_id)
                continue

            if not line:
                continue

            message = SerialMessageCodec.decode(line)

            self.dispatch_to_event_bus(
                message.message_type,
                microcontroller_id,
                message.target,
                message.fields,
            )

            self.dispatch_event_to_reaction_bus(
                message.message_type,
                microcontroller_id,
                message.target,
                message.fields,
            )

    def reconnect(self, microcontroller_id: str) -> None:
        if self.reconnect_board is None:
            raise RuntimeError(
                f"Board transport disconnected: {microcontroller_id}"
            )
        for attempt in range(RECONNECT_ATTEMPTS):
            if self.stop_event.is_set():
                return
            try:
                self.reconnect_board(microcontroller_id)
                return
            except Exception as exc:
                if attempt == RECONNECT_ATTEMPTS - 1:
                    raise RuntimeError(
                        f"Could not reconnect board: {microcontroller_id}"
                    ) from exc
                time.sleep(RECONNECT_BACKOFF_SECONDS * (attempt + 1))

    def dispatch_to_event_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, str],
    ) -> None:
        handler = self.event_bus.get_event(
            event_type,
            microcontroller_id,
            event_name,
        )
        if "error" in payload:
            raise RuntimeError(
                f"Hardware event failed for {event_name}: {payload['error']}"
            )

        runtime_payload = {
            field: CommandCompiler.state_value(
                handler.component_type,
                field,
                value,
            )
            for field, value in payload.items()
        }
        handler.perform_work(runtime_payload)

        payload_field, value = next(iter(runtime_payload.items()))
        state_key = CommandCompiler.state_key(
            self.hardware_plan.connections_by_event_route[
                (microcontroller_id, event_name)
            ],
            payload_field,
        )
        unit = CommandCompiler.state_unit(handler.component_type, payload_field)

        self.hardware_runtime.update_state(
            state_key,
            ConnectionState(value=value, unit=unit),
        )

    def dispatch_event_to_reaction_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, str],
    ) -> Future[object | None]:
        future = self.reaction_executor.submit(
            asyncio.run,
            self.reaction_bus.update_reaction_value(
                event_type,
                microcontroller_id,
                event_name,
                payload,
            ),
        )
        return future
