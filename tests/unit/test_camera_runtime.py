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
        frame: object = "frame",
    ) -> None:
        self.opened = opened
        self.read_success = read_success
        self.frame = frame
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self) -> tuple[bool, object]:
        return self.read_success, self.frame

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
    assert CameraRuntime._get_camera_address(
        DeviceCameraSource(device_index=2)
    ) == 2
    assert (
        CameraRuntime._get_camera_address(
            MJPEGSource(stream_url="http://camera/stream")
        )
        == "http://camera/stream"
    )


def test_camera_runtime_opens_captures_and_closes_cameras(
    monkeypatch,
) -> None:
    cameras = [
        _camera("laptop"),
        _camera(
            "robot",
            MJPEGSource(stream_url="http://camera/stream"),
        ),
    ]
    captures = {
        0: FakeCapture(frame="laptop-frame"),
        "http://camera/stream": FakeCapture(frame="robot-frame"),
    }
    addresses: list[int | str] = []

    def capture_factory(address: int | str) -> FakeCapture:
        addresses.append(address)
        return captures[address]

    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        capture_factory,
    )
    runtime = CameraRuntime(hardware_system=HardwareSystem(cameras=cameras))

    runtime.start()
    runtime.start()

    assert addresses == [0, "http://camera/stream"]
    assert runtime.capture_frame("laptop") == "laptop-frame"
    assert runtime.capture_frame("robot") == "robot-frame"

    runtime.close()

    assert all(capture.released for capture in captures.values())
    assert runtime.connection_pool == {}


def test_camera_runtime_releases_connections_when_start_fails(
    monkeypatch,
) -> None:
    first_capture = FakeCapture()
    failed_capture = FakeCapture(opened=False)
    captures = iter([first_capture, failed_capture])
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: next(captures),
    )
    runtime = CameraRuntime(
        hardware_system=HardwareSystem(
            cameras=[_camera("first"), _camera("second")]
        )
    )

    with pytest.raises(RuntimeError, match="Could not start camera runtime"):
        runtime.start()

    assert first_capture.released
    assert failed_capture.released
    assert runtime.connection_pool == {}


def test_camera_runtime_raises_when_frame_capture_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.camera_runtime.cv2.VideoCapture",
        lambda _: FakeCapture(read_success=False),
    )
    runtime = CameraRuntime(hardware_system=HardwareSystem(cameras=[_camera()]))
    runtime.start()

    with pytest.raises(RuntimeError, match="Could not read camera frame"):
        runtime.capture_frame("laptop")

    runtime.close()


def test_camera_runtime_rejects_unknown_camera() -> None:
    runtime = CameraRuntime(hardware_system=HardwareSystem())

    with pytest.raises(RuntimeError, match="Camera does not exist"):
        runtime.capture_frame("missing")
