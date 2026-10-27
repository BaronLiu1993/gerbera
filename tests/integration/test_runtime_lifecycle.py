import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.models.runtime.server.runtime_lifecycle import RuntimeLifecycle


@pytest.fixture(autouse=True)
def verify_firmware(monkeypatch):
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.server.runtime_lifecycle.FirmwareVerifier",
        lambda runtime: SimpleNamespace(verify=lambda: runtime.prepare()),
    )


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
            prepare=lambda: calls.append("firmware.verify"),
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
        storage=SimpleNamespace(prepare=lambda: calls.append("storage.prepare")),
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
        "storage.prepare",
        "firmware.verify",
        "board.start",
        "cameras.start",
        "models.start",
        "worker.start",
        "listener.start",
        "movement.reset",
        "server.run",
        "models.stop",
        "cameras.close",
        "listener.stop",
        "streams.flush",
        "worker.wait",
        "worker.stop",
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
        "storage.prepare",
        "firmware.verify",
        "board.start",
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


def test_partial_board_start_is_cleaned_by_sdk_lifecycle() -> None:
    calls = []
    lifecycle = build_lifecycle(calls)

    def fail_start():
        calls.append("board.partial_start")
        raise RuntimeError("board failed")

    lifecycle.board_runtime.start = fail_start

    async def serve():
        async with lifecycle(SimpleNamespace()):
            raise AssertionError("startup should fail")

    with pytest.raises(RuntimeError, match="board failed"):
        asyncio.run(serve())

    assert calls[-1] == "board.close"


def test_interrupted_camera_start_cleans_partial_dependencies() -> None:
    calls = []
    lifecycle = build_lifecycle(calls)

    def interrupt_start():
        raise KeyboardInterrupt()

    lifecycle.camera_runtime.start = interrupt_start

    async def serve():
        async with lifecycle(SimpleNamespace()):
            raise AssertionError("startup should not complete")

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(serve())

    assert calls[-2:] == ["cameras.close", "board.close"]


def test_firmware_mismatch_stops_startup_before_hardware_starts(monkeypatch) -> None:
    calls = []
    lifecycle = build_lifecycle(calls)

    def fail_verification():
        calls.append("firmware.verify")
        raise RuntimeError("firmware mismatch")

    lifecycle.board_runtime.prepare = fail_verification

    async def serve():
        async with lifecycle(SimpleNamespace()):
            raise AssertionError("startup should fail")

    with pytest.raises(RuntimeError, match="firmware mismatch"):
        asyncio.run(serve())

    assert calls == ["storage.prepare", "firmware.verify"]


def test_movement_reset_receives_command_response_after_listener_start() -> None:
    from gerbera_sdk.gerbera_runtime import GerberaRuntime
    from gerbera_sdk.models.hardware.connection import Connection
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
    from gerbera_sdk.models.hardware.microcontroller import Microcontroller
    from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec
    from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
    from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry

    motor = Connection(name="motor", component_type="sg90", pins={"signal": "9"}, description="Joint motor")
    hardware = HardwareSystem(name="robot", microcontrollers=[Microcontroller(
        name="board", device_id="board-1", port="/dev/test", fqbn="arduino:avr:uno", connections=[motor],
    )])
    plan = GerberaRuntime.validate_hardware(hardware)
    responses = CommandResponseRegistry()
    calls = []
    lifecycle = build_lifecycle(calls)
    results = []

    def write_command(command):
        if "listener.start" in calls:
            message = SerialMessageCodec.decode(command)
            responses.resolve(message.fields["command_id"], {"angle": "0"})

    boards = SimpleNamespace(get_transport=lambda board_id: SimpleNamespace(write=write_command))
    commands = CommandExecutor(plan, boards, responses, timeout_seconds=0.01)
    commands.bind_actions()
    lifecycle.movement_runtime.reset_motors_to_standard_position = lambda: results.append(
        motor.perform_action("WRITE", {"angle": 0.0})
    )

    with lifecycle.start_resources():
        pass

    assert results == [{"success": True, "value": {"angle": "0"}}]
