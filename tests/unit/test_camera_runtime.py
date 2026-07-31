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


def test_capture_frame_reads_one_image_and_releases_capture(
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

    runtime.capture_frame(camera.id, {})
    frame = camera.latest_frame

    assert captured_addresses == [2]
    assert frame is not None
    assert frame.image is image
    assert camera.latest_frame is frame
    assert capture.released


@pytest.mark.parametrize(
    ("capture", "message"),
    [
        (FakeCapture(opened=False), "Could not open camera: laptop"),
        (FakeCapture(read_success=False), "Could not read camera frame: laptop"),
    ],
)
def test_capture_frame_releases_capture_on_failure(
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
        runtime.capture_frame(camera.id, {})

    assert camera.latest_frame is None
    assert capture.released


def test_capture_loop_updates_frame_and_runs_subscribed_models(
    monkeypatch,
) -> None:
    predictions = []
    model = SimpleNamespace(
        model_name="test-model",
        predict=lambda frame: predictions.append(frame)
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

    assert camera.latest_frame is predictions[0]
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
