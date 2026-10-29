from collections.abc import Mapping
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from queue import Queue
import threading

from serial import SerialException

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.runtime.boards.board_transport import BoardTransport
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.commands.payload_contract import validate_payload
from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.models.runtime.commands.command_response import (
    CommandResponseRegistry, CommandRoute, CommandReply,
)
from gerbera_sdk.models.runtime.state.hardware_runtime import (
    ConnectionState,
    HardwareRuntime,
)
from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec

COMMAND_ID_FIELD = "command_id"
REACTION_QUEUE_CAPACITY = 128


class ListenerStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class BoardListenerHealth:
    status: ListenerStatus = ListenerStatus.STARTING
    last_error: str | None = None
    last_successful_message_at: str | None = None
    malformed_message_count: int = 0

    def snapshot(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "last_error": self.last_error,
            "last_successful_message_at": self.last_successful_message_at,
            "malformed_message_count": self.malformed_message_count,
        }


@dataclass
class EventListener:
    hardware_plan: HardwarePlan
    transport_pool: Mapping[str, BoardTransport]

    event_bus: EventBus
    reaction_bus: ReactionBus
    hardware_runtime: HardwareRuntime
    command_responses: CommandResponseRegistry

    reaction_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gerbera-reaction-callback",
        )
    )
    reaction_queue: Queue[tuple[tuple[str, str, str], dict[str, str]]] = field(
        default_factory=lambda: Queue(maxsize=REACTION_QUEUE_CAPACITY),
        init=False,
        repr=False,
    )
    reaction_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    reaction_worker_running: bool = field(default=False, init=False)
    dropped_reaction_event_count: int = field(default=0, init=False)
    threads: dict[str, threading.Thread] = field(
        default_factory=dict
    )
    stop_event: threading.Event = field(default_factory=threading.Event)
    lifecycle_lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )
    health: dict[str, BoardListenerHealth] = field(default_factory=dict)
    health_lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def create_listeners(self) -> None:
        with self.lifecycle_lock:
            self.stop_event.clear()
            for board in self.hardware_plan.boards:
                microcontroller_id = board.microcontroller_id
                self.set_status(
                    microcontroller_id,
                    ListenerStatus.STARTING,
                )

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

        with self.reaction_lock:
            while not self.reaction_queue.empty():
                self.reaction_queue.get_nowait()

        self.command_responses.fail_all(
            "Event listeners are stopping"
        )

        for transport in list(self.transport_pool.values()):
            transport.cancel_read()

        alive_threads = {}
        for microcontroller_id, thread in threads:
            thread.join(timeout=timeout)
            if thread.is_alive():
                alive_threads[microcontroller_id] = thread

        with self.lifecycle_lock:
            self.threads = alive_threads

        for microcontroller_id, _ in threads:
            if microcontroller_id not in alive_threads:
                self.set_status(
                    microcontroller_id,
                    ListenerStatus.STOPPED,
                )

        self.reaction_executor.shutdown(wait=True, cancel_futures=True)

        if alive_threads:
            names = ", ".join(thread.name for thread in alive_threads.values())
            raise RuntimeError(f"Event listener threads did not stop: {names}")

    def listen_loop(self, microcontroller_id: str) -> None:
        self.set_status(microcontroller_id, ListenerStatus.RUNNING)
        while not self.stop_event.is_set():
            try:
                transport = self.transport_pool[microcontroller_id]
                line = transport.readline()
            except (KeyError, OSError, SerialException) as exc:
                if self.stop_event.is_set():
                    return
                self.command_responses.fail_board(
                    microcontroller_id,
                    f"Board transport disconnected: {exc}",
                )
                self.record_terminal_failure(microcontroller_id, exc)
                return

            if not line:
                continue

            try:
                self.process_message(microcontroller_id, line)
            except (KeyError, RuntimeError, StopIteration, ValueError) as exc:
                self.record_rejected_message(microcontroller_id, exc)
            except Exception as exc:
                self.record_terminal_failure(microcontroller_id, exc)
                return

        self.set_status(microcontroller_id, ListenerStatus.STOPPED)

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
        self.record_success(microcontroller_id)

    def resolve_command_response(self, route: CommandRoute, payload: dict[str, str]) -> bool:
        command_id = payload.pop(COMMAND_ID_FIELD, None)
        if command_id is None:
            return False
        if not self.command_responses.resolve(CommandReply(command_id, route, dict(payload))):
            raise ValueError(f"Unknown command response: {command_id}")
        if "error" in payload:
            payload.clear()
        return True

    def dispatch_to_event_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, str],
    ) -> None:
        connection = self.hardware_plan.connections_by_event_route[(microcontroller_id, event_name)]
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

    def set_status(
        self,
        microcontroller_id: str,
        status: ListenerStatus,
    ) -> None:
        with self.health_lock:
            board_health = self.health.setdefault(
                microcontroller_id,
                BoardListenerHealth(),
            )
            board_health.status = status
            if status == ListenerStatus.RUNNING:
                board_health.last_error = None

    def record_success(self, microcontroller_id: str) -> None:
        with self.health_lock:
            board_health = self.health.setdefault(
                microcontroller_id,
                BoardListenerHealth(),
            )
            board_health.last_successful_message_at = datetime.now(
                timezone.utc
            ).isoformat()

    def record_rejected_message(
        self,
        microcontroller_id: str,
        error: Exception,
    ) -> None:
        with self.health_lock:
            board_health = self.health.setdefault(
                microcontroller_id,
                BoardListenerHealth(),
            )
            board_health.last_error = str(error)
            board_health.malformed_message_count += 1

    def record_terminal_failure(
        self,
        microcontroller_id: str,
        error: Exception,
    ) -> None:
        with self.health_lock:
            board_health = self.health.setdefault(
                microcontroller_id,
                BoardListenerHealth(),
            )
            board_health.status = ListenerStatus.FAILED
            board_health.last_error = str(error)

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

    def process_reaction_queue(self) -> None:
        while True:
            with self.reaction_lock:
                if self.stop_event.is_set() or self.reaction_queue.empty():
                    self.reaction_worker_running = False
                    return
                event_key, payload = self.reaction_queue.get_nowait()
            try:
                asyncio.run(self.reaction_bus.update_reaction_value(event_key, payload))
            except Exception as exc:
                self.record_rejected_message(event_key[1], exc)

    def readiness_reasons(self) -> tuple[str, ...]:
        health = self.get_health()
        return tuple(
            f"Board listener unavailable: {board.microcontroller_id}"
            for board in self.hardware_plan.boards
            if health.get(board.microcontroller_id, {}).get("status") != ListenerStatus.RUNNING
        )
