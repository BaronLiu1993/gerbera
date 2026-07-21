from types import SimpleNamespace

import pytest

from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@pytest.mark.parametrize("server_fails", [False, True])
def test_runtime_orchestrates_startup_and_shutdown_in_order(
    monkeypatch,
    server_fails: bool,
) -> None:
    calls: list[str] = []
    hardware_system = HardwareSystem(description="test")

    def run_server(**kwargs) -> None:
        calls.append("server.run")
        if server_fails:
            raise RuntimeError("server failed")

    board_runtime = SimpleNamespace(
        start=lambda: calls.append("board.start"),
        close=lambda: calls.append("board.close"),
    )
    database_runtime = SimpleNamespace(
        start=lambda: calls.append("database.start"),
        stop=lambda: calls.append("database.stop"),
    )
    server_runtime = SimpleNamespace(
        hardware_system=hardware_system,
        _register_events=lambda: calls.append("events.register"),
        _start_event_listener=lambda: calls.append("listener.start"),
        _stop_event_listener=lambda: calls.append("listener.stop"),
        stream_controller=SimpleNamespace(
            flush_all=lambda: calls.append("streams.flush")
        ),
        app=SimpleNamespace(run=run_server),
    )

    monkeypatch.setattr(GerberaRuntime, "_build_board_runtime", lambda _: board_runtime)
    monkeypatch.setattr(GerberaRuntime, "_build_event_worker", lambda: object())
    monkeypatch.setattr(
        GerberaRuntime,
        "_build_database_runtime",
        lambda hardware, worker: database_runtime,
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_build_server_runtime",
        lambda **kwargs: server_runtime,
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_register_server_runtime_tools",
        lambda runtime: calls.append("tools.register"),
    )

    if server_fails:
        with pytest.raises(RuntimeError, match="server failed"):
            GerberaRuntime.run(hardware_system)
    else:
        GerberaRuntime.run(hardware_system)

    assert calls == [
        "board.start",
        "database.start",
        "events.register",
        "tools.register",
        "listener.start",
        "server.run",
        "listener.stop",
        "streams.flush",
        "database.stop",
        "board.close",
    ]
