from collections.abc import Mapping
import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import threading

from serial import SerialException

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.runtime.board_runtime import SerialConnection
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.hardware_runtime import (
    ConnectionState,
    HardwareRuntime,
)
from gerbera_sdk.models.runtime.serial_protocol import SerialMessageCodec


@dataclass
class EventListener:
    hardware_plan: HardwarePlan
    serial_pool: Mapping[str, SerialConnection]

    event_bus: EventBus
    reaction_bus: ReactionBus
    hardware_runtime: HardwareRuntime

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

        for serial_connection in self.serial_pool.values():
            serial_connection.cancel_read()

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

    def listen_loop(self, microcontroller_id) -> None:
        serial_connection = self.serial_pool[microcontroller_id]
        while not self.stop_event.is_set():
            try:
                line = serial_connection.readline()
            except (OSError, SerialException):
                if self.stop_event.is_set():
                    return
                raise

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
