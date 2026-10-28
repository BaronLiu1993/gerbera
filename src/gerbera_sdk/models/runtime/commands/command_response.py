from collections.abc import Mapping
from dataclasses import dataclass, field
import threading
import uuid
from typing import Annotated

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass as schema_dataclass
from gerbera_sdk.firmware.devices.config_schema import StateFieldConfig
from gerbera_sdk.models.runtime.commands.payload_contract import validate_payload


@schema_dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid"))
class CommandRoute:
    microcontroller_id: Annotated[str, Field(min_length=1)]
    event_name: Annotated[str, Field(min_length=1)]


@schema_dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid"))
class CommandReply:
    command_id: Annotated[str, Field(min_length=1)]
    route: CommandRoute
    payload: dict[str, str]


@dataclass
class PendingCommand:
    command_id: str
    route: CommandRoute
    response_fields: Mapping[str, StateFieldConfig]
    completion: threading.Event = field(default_factory=threading.Event)
    payload: dict[str, str] | None = None
    error: str | None = None


@dataclass
class CommandResponseRegistry:
    pending_commands: dict[str, PendingCommand] = field(default_factory=dict)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def register(self, route: CommandRoute, response_fields: Mapping[str, StateFieldConfig]) -> PendingCommand:
        if not isinstance(route, CommandRoute):
            raise TypeError("Command registration requires an explicit route")
        pending = PendingCommand(
            command_id=uuid.uuid4().hex,
            route=route,
            response_fields=response_fields,
        )
        with self.lock:
            self.pending_commands[pending.command_id] = pending
        return pending

    def resolve(
        self,
        reply: CommandReply,
    ) -> bool:
        with self.lock:
            pending = self.pending_commands.get(reply.command_id)
            if pending is None:
                return False
            if reply.route != pending.route:
                raise ValueError("Command response route does not match its owner")
            if "error" in reply.payload:
                if set(reply.payload) != {"error"} or not reply.payload["error"].strip():
                    raise ValueError("Invalid command error payload")
            else:
                validate_payload(reply.payload, pending.response_fields)
            self.pending_commands.pop(reply.command_id)
            if "error" in reply.payload:
                pending.error = reply.payload["error"]
            else:
                pending.payload = dict(reply.payload)
            pending.completion.set()
        return True

    def fail(self, command_id: str, error: str) -> bool:
        pending = self.remove(command_id)
        if pending is None:
            return False
        pending.error = error
        pending.completion.set()
        return True

    def fail_board(self, microcontroller_id: str, error: str) -> None:
        with self.lock:
            matching = [
                pending
                for pending in self.pending_commands.values()
                if pending.route.microcontroller_id == microcontroller_id
            ]
            for pending in matching:
                self.pending_commands.pop(pending.command_id, None)
        self.fail_commands(matching, error)

    def fail_all(self, error: str) -> None:
        with self.lock:
            pending = list(self.pending_commands.values())
            self.pending_commands.clear()
        self.fail_commands(pending, error)

    def wait(
        self,
        pending: PendingCommand,
        timeout_seconds: float,
    ) -> dict[str, str]:
        if not pending.completion.wait(timeout_seconds):
            self.remove(pending.command_id)
            raise TimeoutError(
                f"Board command response timed out: {pending.command_id}"
            )
        if pending.error is not None:
            raise RuntimeError(pending.error)
        if pending.payload is None:
            raise RuntimeError(f"Board command completed without a response: {pending.command_id}")
        return pending.payload

    def remove(self, command_id: str) -> PendingCommand | None:
        with self.lock:
            return self.pending_commands.pop(command_id, None)

    @staticmethod
    def fail_commands(
        pending_commands: list[PendingCommand],
        error: str,
    ) -> None:
        for pending in pending_commands:
            pending.error = error
            pending.completion.set()
