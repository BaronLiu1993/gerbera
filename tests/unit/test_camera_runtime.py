import threading
from types import SimpleNamespace

import numpy as np
import pytest

from gerbera_sdk.models.hardware.camera import (
    Camera,
    DeviceCameraSource,
    MJPEGSource,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime


class FakeCapture:
    def __init__(
        self,
        *,
        opened: bool = True,
        read_success: bool = True,
        frame=None,
        on_read=None,
    ) -> None:
        self.opened = opened
        self.read_success = read_success
        self.frame = (
            frame
            if frame is not None
            else np.zeros((2, 2, 3), dtype=np.uint8)
        )
        self.on_read = on_read
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        if self.on_read is not None:
            self.on_read()
        return self.read_success, self.frame

    def release(self) -> None:
        self.released = True


def _camera(
    camera_id: str = "laptop",
    source=None,
) -> Camera:
    return Camera(
        camera_id=camera_id,
        name=camera_id,
        description=f"{camera_id} camera",
        source=source or DeviceCameraSource(device_index=0),
    )


def test_camera_lifecycle_captures_configured_sources_and_releases_them(monkeypatch) -> None:
    cameras = [
        _camera("device", DeviceCameraSource(device_index=2)),
        _camera("network", MJPEGSource(stream_url="http://camera/stream")),
    ]
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=cameras)
    )
    runtime.build_camera_sessions()
    sessions = [runtime.get_camera_session(camera.camera_id) for camera in cameras]
    captures = {
        address: FakeCapture(on_read=lambda session=session: session.stop_event.wait(0.001))
        for address, session in zip((2, "http://camera/stream"), sessions)
    }
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.perception.camera_runtime.cv2.VideoCapture",
        captures.__getitem__,
    )

    try:
        runtime.start()
        for camera, session in zip(cameras, sessions):
            assert runtime.get_camera_session(camera.camera_id) is session
            assert session.thread.is_alive()
            assert np.array_equal(runtime.get_latest_frame(camera.camera_id).image, np.zeros((2, 2, 3)))
    finally:
        runtime.close()

    assert all(capture.released for capture in captures.values())
    assert all(session.thread is None and session.stop_event is None for session in sessions)
    assert runtime.camera_registry == runtime.latest_frames == {}


@pytest.mark.parametrize("capture", [FakeCapture(opened=False), FakeCapture(read_success=False)])
def test_start_propagates_camera_capture_failure(monkeypatch, capture) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.perception.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )

    with pytest.raises(RuntimeError, match="failed before capturing") as exc:
        runtime.start()

    assert isinstance(exc.value.__cause__, RuntimeError)
    assert runtime.get_camera_session(camera.camera_id).thread is None
    assert capture.released


def test_capture_frames_reads_requested_batch(
    monkeypatch,
) -> None:
    camera = _camera()
    expected_image = np.zeros((2, 2, 3), dtype=np.uint8)
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    capture = FakeCapture(frame=expected_image)
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.perception.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )
    sleep_calls = []
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.perception.camera_runtime.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    frames = runtime.capture_frames(
        camera_key=camera.camera_id,
        image_count=3,
        interval_seconds=0.25,
    )

    assert len(frames) == 3
    assert all(
        np.array_equal(frame.image, expected_image)
        for frame in frames
    )
    assert sleep_calls == [0.25, 0.25]
    assert capture.released


@pytest.mark.parametrize(
    ("image_count", "interval_seconds", "message"),
    [
        (0, 0.0, "image_count must be at least 1"),
        (1, -0.1, "interval_seconds cannot be negative"),
    ],
)
def test_capture_frames_rejects_invalid_batch_settings(
    image_count: int,
    interval_seconds: float,
    message: str,
) -> None:
    runtime = CameraRuntime(hardware_system=HardwareSystem(name="test"))

    with pytest.raises(ValueError, match=message):
        runtime.capture_frames(
            camera_key="missing",
            image_count=image_count,
            interval_seconds=interval_seconds,
        )


def test_capture_frames_fails_before_camera_has_a_frame() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()

    with pytest.raises(
        RuntimeError,
        match="Camera has not captured a frame yet",
    ):
        runtime.get_latest_frame(camera.camera_id)


def test_wait_for_first_frame_times_out() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera]),
        startup_timeout_seconds=0.0,
    )
    runtime.build_camera_sessions()

    with pytest.raises(TimeoutError, match="did not capture"):
        runtime.wait_for_first_frame(camera.camera_id)


def test_wait_for_first_frame_rejects_ready_session_without_frame() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    runtime.get_camera_session(camera.camera_id).first_frame_ready.set()

    with pytest.raises(RuntimeError, match="readiness without a frame"):
        runtime.wait_for_first_frame(camera.camera_id)


def test_turn_off_camera_stream_rejects_live_thread_after_timeout() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    session = runtime.get_camera_session(camera.camera_id)
    session.stop_event = threading.Event()
    session.thread = SimpleNamespace(
        join=lambda timeout: None,
        is_alive=lambda: True,
    )

    with pytest.raises(RuntimeError, match="did not stop"):
        runtime.turn_off_camera_stream(camera.camera_id)

    assert session.stop_event.is_set()
    assert session.thread is not None


def test_clean_up_cameras_continues_after_first_stop_error(
    monkeypatch,
) -> None:
    cameras = [_camera("first"), _camera("second")]
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=cameras)
    )
    runtime.build_camera_sessions()
    runtime.get_camera_session("first").thread = SimpleNamespace()
    runtime.get_camera_session("second").thread = SimpleNamespace()
    stop_attempts = []
    first_failure = RuntimeError("first camera failed to stop")

    def stop_camera(camera_key: str) -> None:
        stop_attempts.append(camera_key)
        if camera_key == "first":
            raise first_failure

    monkeypatch.setattr(runtime, "turn_off_camera_stream", stop_camera)

    with pytest.raises(RuntimeError, match="Could not clean up cameras") as exc:
        runtime.close()

    assert stop_attempts == ["first", "second"]
    assert exc.value.__cause__ is first_failure
    assert set(runtime.camera_registry) == {"first", "second"}


def test_camera_runtime_rejects_unknown_camera() -> None:
    runtime = CameraRuntime(hardware_system=HardwareSystem(name="test"))

    with pytest.raises(RuntimeError, match="Camera does not exist"):
        runtime.get_camera_session("missing")
