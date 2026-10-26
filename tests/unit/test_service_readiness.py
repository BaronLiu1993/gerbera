import asyncio
from threading import RLock
from types import SimpleNamespace

import pytest
import httpx
from starlette.applications import Starlette

from gerbera_harness.api.readiness import install_readiness
from gerbera_harness.runtime.readiness import HarnessReadiness
from gerbera_protocol import ReadinessReport
from gerbera_sdk.models.runtime.readiness import RuntimeReadiness


def thread(alive=True):
    return SimpleNamespace(is_alive=lambda: alive)


@pytest.fixture
def sdk_readiness():
    return RuntimeReadiness(
        boards=SimpleNamespace(
            lock=RLock(), hardware_plan=SimpleNamespace(
                hardware_system_id="robot", boards=[SimpleNamespace(microcontroller_id="board")],
            ), sessions={"board": SimpleNamespace(heartbeat_thread=thread())},
        ),
        cameras=SimpleNamespace(
            lock=RLock(), hardware_system=SimpleNamespace(cameras=[]), camera_registry={},
        ),
        models=SimpleNamespace(lock=RLock(), model_stream_failures={}, model_streams={}),
        listener=SimpleNamespace(get_health=lambda: {"board": {"status": "running"}}),
        worker=SimpleNamespace(thread=thread(), failures=[]),
        phase="ready",
    )


def test_sdk_reports_ready_only_after_all_dependencies_started(sdk_readiness) -> None:
    assert sdk_readiness.snapshot().model_dump() == {
        "protocol_version": "1", "service": "sdk",
        "phase": "ready", "reasons": (), "instance_id": "robot",
    }


@pytest.mark.parametrize("phase, expected_ready", [
    ("starting", False), ("ready", True), ("degraded", False),
    ("failed", False), ("stopping", False),
])
def test_readiness_is_derived_from_phase(phase, expected_ready) -> None:
    report = ReadinessReport(service="sdk", phase=phase)

    assert report.ready is expected_ready


@pytest.mark.parametrize("phase", ["starting", "failed", "stopping"])
def test_sdk_lifecycle_phase_controls_readiness(sdk_readiness, phase) -> None:
    sdk_readiness.phase = phase

    assert sdk_readiness.snapshot().ready is False


@pytest.mark.parametrize("failure", ["board", "listener", "worker", "camera", "model"])
def test_sdk_readiness_detects_failed_runtime_dependencies(sdk_readiness, failure) -> None:
    if failure == "board":
        sdk_readiness.boards.sessions.clear()
    elif failure == "listener":
        sdk_readiness.listener.get_health = lambda: {"board": {"status": "reconnecting"}}
    elif failure == "worker":
        sdk_readiness.worker.failures.append(RuntimeError("write failed"))
    elif failure == "camera":
        sdk_readiness.cameras.hardware_system.cameras.append(SimpleNamespace(camera_id="camera"))
    else:
        sdk_readiness.models.model_stream_failures["model"] = RuntimeError("inference failed")

    report = sdk_readiness.snapshot()

    assert (report.ready, report.phase, bool(report.reasons)) == (False, "degraded", True)


class Tools:
    async def list_tools(self):
        return []


def test_harness_readiness_follows_remote_sdk_readiness() -> None:
    async def dependency():
        return ReadinessReport(service="sdk", phase="degraded")

    report = asyncio.run(HarnessReadiness(Tools(), dependency, phase="ready").snapshot())

    assert (report.ready, report.reasons) == (False, ("Configured SDK is not ready",))


def test_harness_dependency_errors_are_sanitized() -> None:
    async def dependency():
        raise RuntimeError("password=must-not-leak")

    report = asyncio.run(HarnessReadiness(Tools(), dependency, phase="ready").snapshot())

    assert report.reasons == ("Configured SDK readiness unavailable",)


def test_harness_dependency_readiness_is_bounded() -> None:
    async def dependency():
        await asyncio.Event().wait()

    report = asyncio.run(HarnessReadiness(
        Tools(), dependency, phase="ready", dependency_timeout_seconds=0.01,
    ).snapshot())

    assert report.ready is False


@pytest.mark.parametrize("phase, status", [("starting", 503), ("ready", 200), ("stopping", 503)])
def test_harness_http_readiness_is_distinct_from_liveness(phase, status) -> None:
    app = Starlette()
    install_readiness(app, HarnessReadiness(Tools(), phase=phase))

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://harness") as client:
            return (await client.get("/ready")).status_code

    assert asyncio.run(scenario()) == status
