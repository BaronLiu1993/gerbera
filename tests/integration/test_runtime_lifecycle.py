import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.state_runtime import StateRuntime


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
        event_worker=SimpleNamespace(
            start=lambda: calls.append("worker.start"),
            wait_until_idle=lambda: calls.append("worker.wait"),
            stop=lambda: calls.append("worker.stop"),
        ),
        model_runtime=SimpleNamespace(
            turn_on_all_models=lambda: calls.append("models.start"),
            turn_off_all_models=lambda: calls.append("models.stop"),
        ),
        event_listener=SimpleNamespace(
            create_listeners=lambda: calls.append("listener.start"),
            stop_listeners=lambda: calls.append("listener.stop"),
        ),
        event_bus=SimpleNamespace(
            flush_event_buffers=lambda: calls.append("streams.flush"),
        ),
        state_runtime=StateRuntime(),
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
        "worker.start",
        "listener.start",
        "models.start",
        "server.run",
        "models.stop",
        "listener.stop",
        "streams.flush",
        "worker.wait",
        "worker.stop",
        "cameras.clean_up",
        "board.close",
    ]
