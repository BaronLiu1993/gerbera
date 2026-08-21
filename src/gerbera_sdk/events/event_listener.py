from collections.abc import Mapping
import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import threading

from serial import SerialException

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.board_runtime import SerialConnection
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.hardware_runtime import (
    ConnectionState,
    HardwareRuntime,
)


# Runs at runtime
@dataclass
class EventListener:
    hardware_system: HardwareSystem
    serial_pool: Mapping[str, SerialConnection]

    # Where events are stored
    event_bus: EventBus

    # Reaction code

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
    )  # Multiple threads to run the loop
    # Stops every single thread
    stop_event: threading.Event = field(default_factory=threading.Event)
    lifecycle_lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def create_listeners(self) -> None:
        with self.lifecycle_lock:
            self.stop_event.clear()
            for microcontroller in self.hardware_system.microcontrollers:
                microcontroller_id = microcontroller.id

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
            serial_connection.destroy()

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

            if isinstance(line, bytes):
                line = line.decode(errors="ignore")

            line = line.strip()
            if not line:
                continue

            parsed_payload = self.parse_payload(line)
            if parsed_payload is None:
                continue

            event_type, event_name, payload = parsed_payload

            self.dispatch_to_event_bus(
                event_type,
                microcontroller_id,
                event_name,
                payload,
            )

            self.dispatch_event_to_reaction_bus(
                event_type,
                microcontroller_id,
                event_name,
                payload,
            )

    def parse_payload(self, line: str):
        res_payload = {}

        tokens = line.split(",")
        if len(tokens) < 2:
            return None

        event_type, event_name, payload_tokens = tokens[0], tokens[1], tokens[2:]

        for payload_token in payload_tokens:
            if ":" not in payload_token:
                continue

            key, val = payload_token.split(":", 1)
            if key in res_payload:
                raise ValueError("Key already exists")
            res_payload[key] = val

        return event_type, event_name, res_payload

    # disptach the event to event bus
    def dispatch_to_event_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: dict[str, str],
    ) -> None:
        handler = self.event_bus.get_event(
            event_type,
            microcontroller_id,
            event_name,
        )
        handler.perform_work(payload)
        payload_field, value = next(iter(payload.items()))
        state_field = CommandCompiler.state_field(
            handler.component_type,
            payload_field,
        )
        unit = CommandCompiler.state_unit(handler.component_type, payload_field)

        self.hardware_runtime.update_state(
            handler.connection_name,
            handler.component_type,
            state_field,
            ConnectionState(value=value, unit=unit),
        )

    def dispatch_event_to_reaction_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: dict[str, str],
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
