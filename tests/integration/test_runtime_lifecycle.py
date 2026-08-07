import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle


@pytest.mark.parametrize("server_fails", [False, True])
def test_runtime_orchestrates_startup_and_shutdown_in_order(
    server_fails: bool,
) -> None:
    calls: list[str] = []
    lifecycle = RuntimeLifecycle(
        board_runtime=SimpleNamespace(
            start=lambda: calls.append("board.start"),
            close=lambda: calls.append("board.close"),
        ),
        camera_runtime=SimpleNamespace(
            start_cameras=lambda: calls.append("cameras.start"),
            clean_up_cameras=lambda: calls.append("cameras.clean_up"),
        ),
        database_runtime=SimpleNamespace(
            start=lambda: calls.append("database.start"),
            stop=lambda: calls.append("database.stop"),
        ),
        model_runtime=SimpleNamespace(
            turn_on_all_models=lambda: calls.append("models.start"),
            turn_off_all_models=lambda: calls.append("models.stop"),
        ),
        event_listener=SimpleNamespace(
            create_listeners=lambda: calls.append("listener.start"),
            stop_listeners=lambda: calls.append("listener.stop"),
        ),
        stream_controller=SimpleNamespace(
            flush_all=lambda: calls.append("streams.flush"),
        ),
    )

    async def serve() -> None:
        async with lifecycle(SimpleNamespace()):
            calls.append("server.run")
            if server_fails:
                raise RuntimeError("server failed")

    if server_fails:
        with pytest.raises(RuntimeError, match="server failed"):
            asyncio.run(serve())
    else:
        asyncio.run(serve())

    assert calls == [
        "board.start",
        "cameras.start",
        "database.start",
        "listener.start",
        "models.start",
        "server.run",
        "models.stop",
        "listener.stop",
        "streams.flush",
        "database.stop",
        "cameras.clean_up",
        "board.close",
    ]
