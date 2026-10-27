from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime, CameraSession
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime


@pytest.mark.parametrize("alive, expected", [(True, ()), (False, ("Board session unavailable: board-1",))])
def test_board_owner_reports_heartbeat_health(alive, expected) -> None:
    runtime = BoardRuntime(SimpleNamespace(boards=(SimpleNamespace(microcontroller_id="board-1"),)))
    runtime.sessions["board-1"] = SimpleNamespace(heartbeat_thread=Mock(is_alive=lambda: alive))

    assert runtime.readiness_reasons() == expected


def test_board_owner_reports_missing_session() -> None:
    runtime = BoardRuntime(SimpleNamespace(boards=(SimpleNamespace(microcontroller_id="board-1"),)))

    assert runtime.readiness_reasons() == ("Board session unavailable: board-1",)


@pytest.mark.parametrize("failed, expected", [(False, ()), (True, ("Camera unavailable: camera-1",))])
def test_camera_owner_reports_capture_failure(failed, expected) -> None:
    camera = Camera(name="camera", description="test", source=DeviceCameraSource(0), camera_id="camera-1")
    runtime = CameraRuntime(HardwareSystem(name="robot", cameras=[camera]))
    runtime.camera_registry[camera.camera_id] = CameraSession(
        camera, thread=Mock(is_alive=lambda: True), startup_error=RuntimeError("capture failed") if failed else None,
    )

    assert runtime.readiness_reasons() == expected


def test_model_owner_reports_inference_failure() -> None:
    hardware = HardwareSystem(name="robot")
    runtime = ModelRuntime(hardware, CameraRuntime(hardware))
    runtime.model_stream_failures["model-1"] = RuntimeError("prediction failed")

    assert runtime.readiness_reasons() == ("Required inference streams failed",)


@pytest.mark.parametrize("running, expected", [(True, ()), (False, ("Device event storage worker unavailable",))])
def test_storage_worker_reports_thread_health(running, expected) -> None:
    worker = EventWorker(database=Mock())
    worker.thread = Mock(is_alive=lambda: running)

    assert worker.readiness_reasons() == expected


def test_storage_worker_reports_failed_writes() -> None:
    worker = EventWorker(database=Mock())
    worker.thread = Mock(is_alive=lambda: True)
    worker.failures.append(RuntimeError("write failed"))

    assert worker.readiness_reasons() == ("Device event storage worker unavailable",)


@pytest.mark.parametrize("status, expected", [("running", ()), ("reconnecting", ("Board listener unavailable: board-1",))])
def test_listener_owner_reports_reconnection_state(status, expected) -> None:
    dependency = SimpleNamespace()
    listener = EventListener(
        hardware_plan=SimpleNamespace(boards=(SimpleNamespace(microcontroller_id="board-1"),)),
        transport_pool={}, event_bus=dependency, reaction_bus=dependency,
        hardware_runtime=dependency, command_responses=CommandResponseRegistry(),
    )
    listener.get_health = lambda: {"board-1": {"status": status}}
    try:
        assert listener.readiness_reasons() == expected
    finally:
        listener.reaction_executor.shutdown(wait=True)
