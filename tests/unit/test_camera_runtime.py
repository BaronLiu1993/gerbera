import datetime
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.models.hardware.camera import (
    Camera,
    DeviceCameraSource,
    MJPEGSource,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime


class FakeCapture:
    def __init__(
        self,
        *,
        opened: bool = True,
        read_success: bool = True,
        frame=None,
        frames=None,
        on_read=None,
    ) -> None:
        self.opened = opened
        self.read_success = read_success
        self.frame = (
            frame
            if frame is not None
            else np.zeros((2, 2, 3), dtype=np.uint8)
        )
        self.frames = frames
        self.read_count = 0
        self.on_read = on_read
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        if self.on_read is not None:
            self.on_read()
        frame = self.frame
        if self.frames is not None:
            frame = self.frames[self.read_count]
        self.read_count += 1
        return self.read_success, frame

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


def test_camera_address_resolves_supported_sources() -> None:
    assert CameraRuntime.get_camera_address(
        DeviceCameraSource(device_index=2)
    ) == 2
    assert (
        CameraRuntime.get_camera_address(
            MJPEGSource(stream_url="http://camera/stream")
        )
        == "http://camera/stream"
    )


def test_register_cameras_is_idempotent() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )

    runtime.build_camera_sessions()
    first_session = runtime.get_camera_session(camera.camera_id)
    runtime.build_camera_sessions()

    assert runtime.get_camera_session(camera.camera_id) is first_session
    assert first_session.camera is camera


def test_start_starts_every_configured_camera(
    monkeypatch,
) -> None:
    cameras = [_camera("first"), _camera("second")]
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=cameras)
    )
    started = []
    ready = []
    monkeypatch.setattr(
        runtime,
        "turn_on_camera_stream",
        lambda camera_key: started.append(camera_key),
    )
    monkeypatch.setattr(
        runtime,
        "wait_for_first_frame",
        lambda camera_key: ready.append(camera_key),
    )

    runtime.start()

    assert started == ["first", "second"]
    assert ready == ["first", "second"]
    assert set(runtime.camera_registry) == {"first", "second"}


def test_start_propagates_camera_capture_failure(monkeypatch) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    capture = FakeCapture(opened=False)
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
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
    camera.latest_frame = Frame(
        image=np.zeros((2, 2, 3), dtype=np.uint8),
        timestamp=datetime.datetime.now(),
    )
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    capture = FakeCapture(frame=camera.latest_frame.image)
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )
    sleep_calls = []
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    frames = runtime.capture_frames(
        camera_key=camera.camera_id,
        image_count=3,
        interval_seconds=0.25,
    )

    assert len(frames) == 3
    assert all(
        np.array_equal(frame.image, camera.latest_frame.image)
        for frame in frames
    )
    assert sleep_calls == [0.25, 0.25]


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


def test_capture_loop_updates_latest_frame(
    monkeypatch,
) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    session = runtime.get_camera_session(camera.camera_id)
    session.stop_event = threading.Event()
    capture = FakeCapture(on_read=session.stop_event.set)
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )

    runtime.capture_loop(camera.camera_id)

    assert runtime.get_latest_frame(camera.camera_id) is not None
    assert capture.released


def test_turn_on_camera_stream_starts_capture_thread(
    monkeypatch,
) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    created_threads = []

    def build_thread(**kwargs):
        thread = SimpleNamespace(
            start=lambda: None,
            is_alive=lambda: False,
            **kwargs,
        )
        created_threads.append(thread)
        return thread

    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.threading.Thread",
        build_thread,
    )

    runtime.turn_on_camera_stream(camera.camera_id)

    assert created_threads[0].target == runtime.capture_loop
    assert created_threads[0].args == (camera.camera_id,)


def test_wait_for_first_frame_propagates_capture_failure() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    session = runtime.get_camera_session(camera.camera_id)
    failure = RuntimeError("capture failed")
    session.startup_error = failure
    session.first_frame_ready.set()

    with pytest.raises(RuntimeError, match="failed before capturing") as exc:
        runtime.wait_for_first_frame(camera.camera_id)

    assert exc.value.__cause__ is failure


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


def test_turn_off_camera_stream_clears_a_stopped_session() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=[camera])
    )
    runtime.build_camera_sessions()
    session = runtime.get_camera_session(camera.camera_id)
    session.stop_event = threading.Event()
    session.thread = SimpleNamespace(
        join=lambda timeout: None,
        is_alive=lambda: False,
    )

    runtime.turn_off_camera_stream(camera.camera_id)

    assert session.stop_event is None
    assert session.thread is None


def test_clean_up_cameras_stops_streams_and_clears_registry(
    monkeypatch,
) -> None:
    cameras = [_camera("first"), _camera("second")]
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(name="test", cameras=cameras)
    )
    runtime.build_camera_sessions()
    stopped = []
    runtime.get_camera_session("first").thread = SimpleNamespace()
    monkeypatch.setattr(
        runtime,
        "turn_off_camera_stream",
        lambda camera_key: stopped.append(camera_key),
    )

    runtime.close()

    assert stopped == ["first"]
    assert runtime.camera_registry == {}


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
