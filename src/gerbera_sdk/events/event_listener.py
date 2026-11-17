from collections.abc import Mapping
from dataclasses import dataclass, field
import threading

from serial import SerialException

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.boards.board_transport import BoardTransport
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.commands.payload_contract import validate_payload
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.models.runtime.state.hardware_runtime import ConnectionState
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec


@dataclass
class EventListener:
    hardware_system: HardwareSystem
    event_bus: EventBus

    # concurrency tools
    thread_pool: dict[str, threading.Thread] = field(default_factory=dict, init=False)
    stop_event: threading.Event = field(default_factory=threading.Event, init=False)

    def create_listeners(self) -> None:
        if self.stop_event:
            raise RuntimeError("Event listeners are already running")

        boards = self.hardware_system.microcontrollers
        self.thread_pool.clear()
        for board in boards:
            self.thread_pool[board.id] = threading.Thread(
                target=self.listen_loop,
                args=(board.id,),
                daemon=False,
                name=f"serial-listener-{board.id}",
            )

    def start_listeners(self) -> None:
        if any(thread.ident is not None for thread in self.thread_pool.values()):
            raise RuntimeError("Create new listeners before starting them again")

        self.stop_event.clear()
        try:
            for thread in self.thread_pool.values():
                thread.start()
        except BaseException as error:
            self.stop_listeners()
            raise

    def stop_listeners(self, timeout: float = 2.0) -> None:
        for thread in self.thread_pool.values():
            if thread.ident is not None:
                thread.join(timeout=timeout)

    def listen_loop(self, microcontroller_id: str) -> None:
        while not self.stop_event.is_set():
            try:
                line = transport.readline()

                if not line:
                    continue

                self.process_message(microcontroller_id, line)
            except (KeyError, RuntimeError, StopIteration, ValueError):
                continue
            

    def process_message(
        self,
        microcontroller_id: str,
        line: bytes | str,
    ) -> None:
        message = SerialMessageCodec.decode(line)
        payload = dict(message.fields)
        if message.message_type == "MCP":
            route = CommandRoute(microcontroller_id, message.target)
            if self.resolve_command_response(route, payload):
                if not payload:
                    self.record_success(microcontroller_id)
                    return

        if "error" in payload:
            raise RuntimeError(
                f"Hardware event failed for {message.target}: "
                f"{payload['error']}"
            )

        self.dispatch_to_event_bus(
            message.message_type,
            microcontroller_id,
            message.target,
            payload,
        )
        self.dispatch_event_to_reaction_bus(
            message.message_type,
            microcontroller_id,
            message.target,
            payload,
        )

    def dispatch_to_event_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, str],
    ) -> None:
        connection = next(
            connection
            for board in self.hardware_system.microcontrollers
            if board.id == microcontroller_id
            for connection in board.connections
            if connection.event_name == event_name
        )
        builder = get_device_builder(connection.component_type)
        config = builder.config
        if event_type == "STREAM":
            if not connection.stream_enabled:
                raise ValueError("Streaming is not enabled for this connection")
            field_names = config.stream.payload_fields
        elif event_type == "MCP":
            allowed_fields = {frozenset(command.response_fields) for command in builder.required_commands(connection)}
            if frozenset(payload) not in allowed_fields:
                raise ValueError("Undeclared command event payload fields")
            field_names = tuple(payload)
        else:
            raise ValueError(f"Unsupported hardware event type: {event_type}")
        validate_payload(payload, {name: config.state.fields[name] for name in field_names})
        handler = self.event_bus.get_event(
            event_type,
            microcontroller_id,
            event_name,
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

        for payload_field, value in runtime_payload.items():
            state_key = CommandCompiler.state_key(connection, payload_field)
            unit = CommandCompiler.state_unit(handler.component_type, payload_field)
            self.hardware_runtime.update_state(state_key, ConnectionState(value=value, unit=unit))

    def get_health(self) -> dict[str, dict[str, object]]:
        with self.health_lock:
            return {
                microcontroller_id: board_health.snapshot()
                for microcontroller_id, board_health in self.health.items()
            }

    def dispatch_event_to_reaction_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, str],
    ) -> None:
        with self.reaction_lock:
            if self.stop_event.is_set():
                return
            if self.reaction_queue.full():
                self.reaction_queue.get_nowait()
                self.dropped_reaction_event_count += 1
            self.reaction_queue.put_nowait(((event_type, microcontroller_id, event_name), dict(payload)))
            if not self.reaction_worker_running:
                self.reaction_executor.submit(self.process_reaction_queue)
                self.reaction_worker_running = True
