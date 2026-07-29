import threading
import time

import pytest

from gerbera_sdk.models.hardware.camera import (
    Camera,
    DeviceCameraSource,
    MJPEGSource,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.camera_runtime import (
    CameraRuntime,
    CameraSession,
    camera_address,
)


class FakeCapture:
    def __init__(
        self,
        *,
        opened: bool = True,
        frame: object = "frame",
    ) -> None:
        self.opened = opened
        self.frame = frame
        self.released = False
        self.frame_read = threading.Event()

    def isOpened(self) -> bool:
        return self.opened

    def read(self) -> tuple[bool, object]:
        self.frame_read.set()
        time.sleep(0.001)
        return not self.released, self.frame

    def release(self) -> None:
        self.released = True


def _camera(
    camera_id: str = "laptop",
    source=None,
) -> Camera:
    return Camera(
        id=camera_id,
        name=camera_id,
        description=f"{camera_id} camera",
        source=source or DeviceCameraSource(),
    )


def test_camera_address_resolves_supported_sources() -> None:
    assert camera_address(DeviceCameraSource(device_index=2)) == 2
    assert (
        camera_address(MJPEGSource(stream_url="http://camera/stream"))
        == "http://camera/stream"
    )


def test_camera_session_starts_disabled_and_keeps_only_latest_frame() -> None:
    capture = FakeCapture(frame=object())
    session = CameraSession(
        camera=_camera(),
        capture_factory=lambda _: capture,
    )

    session.start()

    assert session.is_enabled is False
    assert session.get_latest_frame() is None
    assert session._thread is not None
    assert session._thread.daemon is False

    session.enable()
    assert capture.frame_read.wait(timeout=1)

    deadline = time.monotonic() + 1
    while session.get_latest_frame() is None and time.monotonic() < deadline:
        time.sleep(0.001)

    assert session.get_latest_frame() is capture.frame

    session.disable()
    assert session.is_enabled is False

    session.close()
    assert capture.released
    assert session._thread is None


def test_camera_session_releases_capture_that_did_not_open() -> None:
    capture = FakeCapture(opened=False)
    session = CameraSession(
        camera=_camera(),
        capture_factory=lambda _: capture,
    )

    with pytest.raises(RuntimeError, match="Could not open camera"):
        session.start()

    assert capture.released


def test_camera_runtime_manages_one_session_per_camera() -> None:
    cameras = [
        _camera("laptop"),
        _camera(
            "robot",
            MJPEGSource(stream_url="http://camera/stream"),
        ),
    ]
    system = HardwareSystem(cameras=cameras)
    captures: dict[str, FakeCapture] = {}

    def session_factory(camera: Camera) -> CameraSession:
        capture = FakeCapture(frame=camera.id)
        captures[camera.id] = capture
        return CameraSession(
            camera=camera,
            capture_factory=lambda _: capture,
        )

    runtime = CameraRuntime(
        hardware_system=system,
        session_factory=session_factory,
    )

    runtime.start()
    runtime.start()

    assert set(runtime.sessions) == {"laptop", "robot"}
    assert len(captures) == 2

    runtime.start_stream("laptop")
    assert captures["laptop"].frame_read.wait(timeout=1)

    deadline = time.monotonic() + 1
    while runtime.get_latest_frame("laptop") is None:
        if time.monotonic() >= deadline:
            pytest.fail("Camera did not publish a frame")
        time.sleep(0.001)

    assert runtime.get_latest_frame("laptop") == "laptop"
    assert runtime.get_session("laptop").is_enabled
    assert runtime.get_session("robot").is_enabled is False

    runtime.stop_stream("laptop")
    runtime.close()

    assert all(capture.released for capture in captures.values())
    assert runtime.sessions == {}


def test_camera_runtime_keeps_session_tracked_when_shutdown_fails() -> None:
    class FailingSession:
        def __init__(self, camera: Camera) -> None:
            self.camera = camera

        def start(self) -> None:
            return None

        def close(self) -> None:
            raise RuntimeError("worker still running")

    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[_camera()]),
        session_factory=FailingSession,
    )
    runtime.start()

    with pytest.raises(RuntimeError, match="Could not stop camera runtime"):
        runtime.close()

    assert set(runtime.sessions) == {"laptop"}
