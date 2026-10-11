from collections.abc import Mapping
from dataclasses import dataclass, field
import threading
import uuid


@dataclass
class PendingCommand:
    command_id: str
    microcontroller_id: str
    completion: threading.Event = field(default_factory=threading.Event)
    payload: dict[str, str] | None = None
    error: str | None = None


@dataclass
class CommandAcknowledgementRegistry:
    pending_commands: dict[str, PendingCommand] = field(default_factory=dict)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def register(self, microcontroller_id: str) -> PendingCommand:
        pending = PendingCommand(
            command_id=uuid.uuid4().hex,
            microcontroller_id=microcontroller_id,
        )
        with self.lock:
            self.pending_commands[pending.command_id] = pending
        return pending

    def resolve(
        self,
        command_id: str,
        payload: Mapping[str, str],
    ) -> bool:
        pending = self._remove(command_id)
        if pending is None:
            return False
        pending.payload = dict(payload)
        pending.completion.set()
        return True

    def fail(self, command_id: str, error: str) -> bool:
        pending = self._remove(command_id)
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
                if pending.microcontroller_id == microcontroller_id
            ]
            for pending in matching:
                self.pending_commands.pop(pending.command_id, None)
        self._fail_commands(matching, error)

    def fail_all(self, error: str) -> None:
        with self.lock:
            pending = list(self.pending_commands.values())
            self.pending_commands.clear()
        self._fail_commands(pending, error)

    def wait(
        self,
        pending: PendingCommand,
        timeout_seconds: float,
    ) -> dict[str, str]:
        if not pending.completion.wait(timeout_seconds):
            self._remove(pending.command_id)
            raise TimeoutError(
                f"Board acknowledgement timed out: {pending.command_id}"
            )
        if pending.error is not None:
            raise RuntimeError(pending.error)
        return pending.payload or {}

    def _remove(self, command_id: str) -> PendingCommand | None:
        with self.lock:
            return self.pending_commands.pop(command_id, None)

    @staticmethod
    def _fail_commands(
        pending_commands: list[PendingCommand],
        error: str,
    ) -> None:
        for pending in pending_commands:
            pending.error = error
            pending.completion.set()
