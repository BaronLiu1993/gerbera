import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle


def build_lifecycle(
    calls: list[str],
    *,
    model_start_error: Exception | None = None,
) -> RuntimeLifecycle:
    def start_models() -> None:
        calls.append("models.start")
        if model_start_error is not None:
            raise model_start_error

    return RuntimeLifecycle(
        board_runtime=SimpleNamespace(
            start=lambda: calls.append("board.start"),
            close=lambda: calls.append("board.close"),
        ),
        camera_runtime=SimpleNamespace(
            start=lambda: calls.append("cameras.start"),
            close=lambda: calls.append("cameras.close"),
        ),
        event_worker=SimpleNamespace(
            start=lambda: calls.append("worker.start"),
            wait_until_idle=lambda: calls.append("worker.wait"),
            stop=lambda: calls.append("worker.stop"),
        ),
        model_runtime=SimpleNamespace(
            turn_on_all_model_streams=start_models,
            turn_off_all_model_streams=lambda: calls.append("models.stop"),
        ),
        event_listener=SimpleNamespace(
            create_listeners=lambda: calls.append("listener.start"),
            stop_listeners=lambda: calls.append("listener.stop"),
        ),
        event_bus=SimpleNamespace(
            flush_event_buffers=lambda: calls.append("streams.flush"),
        ),
        hardware_runtime=SimpleNamespace(name="hardware-runtime"),
        movement_runtime=SimpleNamespace(
            reset_motors_to_standard_position=lambda: calls.append(
                "movement.reset"
            )
        ),
    )


@pytest.mark.parametrize("server_fails", [False, True])
def test_runtime_orchestrates_resources_in_dependency_order(
    server_fails: bool,
) -> None:
    calls: list[str] = []
    lifecycle = build_lifecycle(calls)

    async def serve() -> None:
        async with lifecycle(SimpleNamespace()) as resources:
            assert resources["hardware_runtime"].name == "hardware-runtime"
            assert resources["movement_runtime"] is lifecycle.movement_runtime
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
        "movement.reset",
        "cameras.start",
        "models.start",
        "worker.start",
        "listener.start",
        "server.run",
        "listener.stop",
        "streams.flush",
        "worker.wait",
        "worker.stop",
        "models.stop",
        "cameras.close",
        "board.close",
    ]


def test_runtime_cleans_started_dependencies_when_model_start_fails() -> None:
    calls: list[str] = []
    failure = RuntimeError("model startup failed")
    lifecycle = build_lifecycle(calls, model_start_error=failure)

    async def serve() -> None:
        async with lifecycle(SimpleNamespace()):
            raise AssertionError("runtime should not enter the server context")

    with pytest.raises(RuntimeError, match="model startup failed") as exc:
        asyncio.run(serve())

    assert exc.value is failure
    assert calls == [
        "board.start",
        "movement.reset",
        "cameras.start",
        "models.start",
        "models.stop",
        "cameras.close",
        "board.close",
    ]


def test_runtime_skips_movement_reset_when_movement_is_not_configured() -> None:
    calls: list[str] = []
    lifecycle = build_lifecycle(calls)
    lifecycle.movement_runtime = None

    async def serve() -> None:
        async with lifecycle(SimpleNamespace()):
            calls.append("server.run")

    asyncio.run(serve())

    assert "movement.reset" not in calls
