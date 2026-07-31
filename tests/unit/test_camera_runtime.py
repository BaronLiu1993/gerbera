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
    subscribed_models=None,
) -> Camera:
    return Camera(
        id=camera_id,
        name=camera_id,
        description=f"{camera_id} camera",
        source=source or DeviceCameraSource(device_index=0),
        subscribed_models=subscribed_models or [],
    )


def test_camera_address_resolves_supported_sources() -> None:
    assert CameraRuntime._get_camera_address(
        DeviceCameraSource(device_index=2)
    ) == 2
    assert (
        CameraRuntime._get_camera_address(
            MJPEGSource(stream_url="http://camera/stream")
        )
        == "http://camera/stream"
    )


def test_register_cameras_is_idempotent() -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )

    runtime.register_cameras()
    first_session = runtime.get_camera_session(camera.id)
    runtime.register_cameras()

    assert runtime.get_camera_session(camera.id) is first_session
    assert first_session.camera is camera


def test_capture_frames_defaults_to_one_image_and_releases_capture(
    monkeypatch,
) -> None:
    image = np.ones((3, 4, 3), dtype=np.uint8)
    capture = FakeCapture(frame=image)
    captured_addresses = []
    camera = _camera(source=DeviceCameraSource(device_index=2))
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda address: captured_addresses.append(address) or capture,
    )

    runtime.capture_frames(camera.id, {})
    frame = camera.latest_frame

    assert captured_addresses == [2]
    assert frame is not None
    assert frame.image is image
    assert camera.latest_frame is frame
    assert capture.released


def test_capture_frames_stores_subscribed_model_output(
    monkeypatch,
) -> None:
    expected_output = {"environment_name": "workshop"}
    predicted_batches = []
    model = SimpleNamespace(
        name="test-model",
        predict=lambda frames: (
            predicted_batches.append(frames) or expected_output
        ),
    )
    camera = _camera(subscribed_models=[model])
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: FakeCapture(),
    )

    runtime.capture_frames(camera.id, {"test-model": True})

    assert camera.latest_output is expected_output
    assert predicted_batches == [[camera.latest_frame]]


def test_capture_frames_batches_images_into_one_model_call(
    monkeypatch,
) -> None:
    images = [
        np.full((2, 2, 3), value, dtype=np.uint8)
        for value in range(3)
    ]
    capture = FakeCapture(frames=images)
    predicted_batches = []
    model = SimpleNamespace(
        name="test-model",
        predict=lambda frames: predicted_batches.append(frames),
    )
    camera = _camera(subscribed_models=[model])
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
    sleep_calls = []
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    runtime.capture_frames(
        camera_key=camera.id,
        running_models={"test-model": True},
        image_count=3,
        interval_seconds=0.25,
    )

    assert len(predicted_batches) == 1
    assert len(predicted_batches[0]) == len(images)
    assert all(
        frame.image is image
        for frame, image in zip(predicted_batches[0], images)
    )
    assert camera.latest_frame is predicted_batches[0][-1]
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
    runtime = CameraRuntime(hardware_system=HardwareSystem())

    with pytest.raises(ValueError, match=message):
        runtime.capture_frames(
            camera_key="missing",
            running_models={},
            image_count=image_count,
            interval_seconds=interval_seconds,
        )


@pytest.mark.parametrize(
    ("capture", "message"),
    [
        (FakeCapture(opened=False), "Could not open camera: laptop"),
        (FakeCapture(read_success=False), "Could not read camera frame: laptop"),
    ],
)
def test_capture_frames_releases_capture_on_failure(
    monkeypatch,
    capture,
    message: str,
) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )

    with pytest.raises(RuntimeError, match=message):
        runtime.capture_frames(camera.id, {})

    assert camera.latest_frame is None
    assert capture.released


def test_capture_loop_updates_frame_and_runs_subscribed_models(
    monkeypatch,
) -> None:
    predictions = []
    model = SimpleNamespace(
        name="test-model",
        predict=lambda frames: predictions.append(frames)
    )
    camera = _camera(subscribed_models=[model])
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
    session = runtime.get_camera_session(camera.id)
    session._stop_event = threading.Event()
    capture = FakeCapture(on_read=session._stop_event.set)
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: capture,
    )

    runtime._capture_loop(camera.id, {"test-model": True})

    assert camera.latest_frame is predictions[0][0]
    assert camera.latest_output is None
    assert capture.released


def test_turn_on_camera_stream_passes_models_to_capture_thread(
    monkeypatch,
) -> None:
    camera = _camera()
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=[camera])
    )
    runtime.register_cameras()
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

    runtime.turn_on_camera_stream(
        camera.id,
        {"openai-vision-language-model": True},
    )

    assert created_threads[0].target == runtime._capture_loop
    assert created_threads[0].args == (
        camera.id,
        {"openai-vision-language-model": True},
    )


def test_clean_up_cameras_stops_streams_and_clears_registry(
    monkeypatch,
) -> None:
    cameras = [_camera("first"), _camera("second")]
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(cameras=cameras)
    )
    runtime.register_cameras()
    stopped = []
    runtime.get_camera_session("first")._thread = SimpleNamespace()
    monkeypatch.setattr(
        runtime,
        "turn_off_camera_stream",
        lambda camera_key: stopped.append(camera_key),
    )

    runtime.clean_up_cameras()

    assert stopped == ["first"]
    assert runtime.camera_registry == {}


def test_camera_runtime_rejects_unknown_camera() -> None:
    runtime = CameraRuntime(hardware_system=HardwareSystem())

    with pytest.raises(RuntimeError, match="Camera does not exist"):
        runtime.get_camera_session("missing")
