from dataclasses import replace
from types import MappingProxyType
from types import SimpleNamespace

import pytest

from gerbera_sdk.firmware.board_definitions import ARDUINO_UNO
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedBoard
from gerbera_sdk.models.hardware.microcontroller import RuntimeWatchdogConfig
from gerbera_sdk.models.runtime.board_runtime import (
    BoardRuntime,
    BoardSession,
    SerialConnection,
)


class HandshakeConnection:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.command = ""

    def write(self, command: str) -> None:
        self.command = command

    def readline(self) -> bytes:
        challenge = self.command.rsplit("challenge:", 1)[1]
        return self.response.replace(b"{challenge}", challenge.encode())


class ScriptedConnection:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = responses
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)

    def readline(self) -> bytes:
        return self.responses.pop(0)


def make_board() -> ResolvedBoard:
    return ResolvedBoard(
        microcontroller_id="board-1",
        name="board",
        port="/dev/board-1",
        baud_rate=115200,
        definition=ARDUINO_UNO,
        connections=(),
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
        contract_digest="abc123",
    )


def make_plan() -> HardwarePlan:
    board = make_board()
    return HardwarePlan(
        hardware_system_id="system-1",
        boards=(board,),
        boards_by_id=MappingProxyType({"board-1": board}),
        connections_by_key=MappingProxyType({}),
        connections_by_event_route=MappingProxyType({}),
    )


def test_board_contract_handshake_accepts_exact_match() -> None:
    connection = HandshakeConnection(
        b"HANDSHAKE,__gerbera__,protocol:1,board:board-1,"
        b"digest:abc123,challenge:{challenge}\n"
    )

    session_id = BoardRuntime.verify_contract(make_board(), connection)

    assert connection.command.startswith(
        "HANDSHAKE,__gerbera__,challenge:"
    )
    assert session_id == connection.command.rsplit("challenge:", 1)[1]


def test_board_contract_handshake_rejects_stale_firmware() -> None:
    connection = HandshakeConnection(
        b"HANDSHAKE,__gerbera__,protocol:1,board:board-1,"
        b"digest:stale,challenge:{challenge}\n"
    )

    with pytest.raises(RuntimeError, match="does not match"):
        BoardRuntime.verify_contract(make_board(), connection)


def test_board_contract_handshake_rejects_timeout() -> None:
    connection = HandshakeConnection(b"")

    with pytest.raises(TimeoutError, match="timed out"):
        BoardRuntime.verify_contract(make_board(), connection)


def test_component_checks_require_an_exact_pass() -> None:
    board = replace(
        make_board(),
        connections=(SimpleNamespace(name="sensor"),),
    )
    connection = ScriptedConnection(
        [b"CHECK,board-1.sensor,status:pass,session:session-1\n"]
    )

    BoardRuntime.verify_components(board, connection, "session-1")

    assert connection.commands == [
        "CHECK,board-1.sensor,session:session-1"
    ]


def test_component_check_failure_is_not_retried() -> None:
    board = replace(
        make_board(),
        connections=(SimpleNamespace(name="sensor"),),
    )
    connection = ScriptedConnection(
        [
            b"CHECK,board-1.sensor,status:fail,"
            b"error:component_check_failed,session:session-1\n"
        ]
    )

    with pytest.raises(RuntimeError, match="Component check failed"):
        BoardRuntime.verify_components(board, connection, "session-1")

    assert len(connection.commands) == 1


def test_start_requires_ready_for_the_current_session() -> None:
    connection = ScriptedConnection(
        [b"START,__gerbera__,state:READY,session:session-1\n"]
    )

    BoardRuntime.start_firmware(connection, "session-1")

    assert connection.commands == [
        "START,__gerbera__,session:session-1"
    ]


def test_board_runtime_registers_connection_after_handshake(
    monkeypatch,
) -> None:
    monkeypatch.setattr(SerialConnection, "connect", lambda *args, **kwargs: None)
    monkeypatch.setattr(BoardRuntime, "verify_contract", lambda *args: "session")
    monkeypatch.setattr(BoardRuntime, "verify_components", lambda *args: None)
    monkeypatch.setattr(BoardRuntime, "start_firmware", lambda *args: None)
    monkeypatch.setattr(BoardRuntime, "send_first_heartbeat", lambda *args: None)
    monkeypatch.setattr(BoardSession, "heartbeat_loop", lambda self: None)
    runtime = BoardRuntime(make_plan())

    runtime.start()

    assert set(runtime.serial_pool) == {"board-1"}
    assert set(runtime.sessions) == {"board-1"}


def test_board_runtime_does_not_register_failed_handshake(monkeypatch) -> None:
    monkeypatch.setattr(SerialConnection, "connect", lambda *args, **kwargs: None)
    monkeypatch.setattr(SerialConnection, "destroy", lambda *args: None)

    def reject_contract(*args) -> None:
        raise RuntimeError("contract mismatch")

    monkeypatch.setattr(BoardRuntime, "verify_contract", reject_contract)
    runtime = BoardRuntime(make_plan())

    with pytest.raises(RuntimeError, match="Could not start"):
        runtime.start()

    assert runtime.serial_pool == {}
