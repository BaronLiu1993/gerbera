import asyncio
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

    board_runtime = SimpleNamespace(
        start=lambda: calls.append("board.start"),
        close=lambda: calls.append("board.close"),
    )
    camera_runtime = SimpleNamespace(
        register_cameras=lambda: calls.append("cameras.register"),
        clean_up_cameras=lambda: calls.append("cameras.clean_up"),
    )
    database_runtime = SimpleNamespace(
        start=lambda: calls.append("database.start"),
        stop=lambda: calls.append("database.stop"),
    )

    monkeypatch.setattr(GerberaRuntime, "_build_board_runtime", lambda _: board_runtime)
    monkeypatch.setattr(
        GerberaRuntime,
        "_build_camera_runtime",
        lambda _: camera_runtime,
    )
    monkeypatch.setattr(GerberaRuntime, "_build_event_worker", lambda: object())
    monkeypatch.setattr(
        GerberaRuntime,
        "_build_database_runtime",
        lambda hardware, worker: database_runtime,
    )
    def build_server_runtime(**kwargs):
        runtime_lifecycle = kwargs["runtime_lifecycle"]
        server_runtime = SimpleNamespace(
            hardware_system=hardware_system,
            _register_events=lambda: calls.append("events.register"),
            _start_event_listener=lambda: calls.append("listener.start"),
            _stop_event_listener=lambda: calls.append("listener.stop"),
            stream_controller=SimpleNamespace(
                flush_all=lambda: calls.append("streams.flush")
            ),
        )

        class App:
            def run(self, **transport_kwargs) -> None:
                async def serve() -> None:
                    async with runtime_lifecycle(self):
                        calls.append("server.run")
                        if server_fails:
                            raise RuntimeError("server failed")

                asyncio.run(serve())

        server_runtime.app = App()
        runtime_lifecycle.bind_server_runtime(server_runtime)
        return server_runtime

    monkeypatch.setattr(
        GerberaRuntime,
        "_build_server_runtime",
        build_server_runtime,
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_build_agent_runtime",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_register_server_runtime_tools",
        lambda runtime: calls.append("tools.register"),
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_register_agent_runtime_tool",
        lambda runtime: calls.append("agent_tool.register"),
    )
    monkeypatch.setattr(
        GerberaRuntime,
        "_register_event_catalog_tool",
        lambda runtime: calls.append("event_catalog_tool.register"),
    )

    if server_fails:
        with pytest.raises(RuntimeError, match="server failed"):
            GerberaRuntime.run(hardware_system)
    else:
        GerberaRuntime.run(hardware_system)

    assert calls == [
        "events.register",
        "tools.register",
        "agent_tool.register",
        "event_catalog_tool.register",
        "board.start",
        "cameras.register",
        "database.start",
        "listener.start",
        "server.run",
        "listener.stop",
        "streams.flush",
        "database.stop",
        "cameras.clean_up",
        "board.close",
    ]
