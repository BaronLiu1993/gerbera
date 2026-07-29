from collections.abc import Callable
from dataclasses import dataclass, field
import threading
from typing import Protocol

from gerbera_sdk.models.hardware.camera import (
    Camera,
    CameraSource,
    DeviceCameraSource,
    MJPEGSource,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
import cv2

CameraAddress = int | str
CameraFrame = object

class VideoCapture(Protocol):
    def isOpened(self) -> bool: ...

    def read(self) -> tuple[bool, CameraFrame]: ...

    def release(self) -> None: ...


CaptureFactory = Callable[[CameraAddress], VideoCapture]


def open_video_capture(address: CameraAddress) -> VideoCapture:
    return cv2.VideoCapture(address)


def camera_address(source: CameraSource) -> CameraAddress:
    if isinstance(source, DeviceCameraSource):
        return source.device_index
    if isinstance(source, MJPEGSource):
        return source.stream_url
    raise TypeError(f"Unsupported camera source: {type(source).__name__}")


@dataclass
class CameraSession:
    camera: Camera
    capture_factory: CaptureFactory = field(
        default=open_video_capture,
        repr=False,
    )
    _enabled: threading.Event = field(
        default_factory=threading.Event,
        init=False,
        repr=False,
    )
    _shutdown: threading.Event = field(
        default_factory=threading.Event,
        init=False,
        repr=False,
    )
    _frame_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _lifecycle_lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )
    _capture: VideoCapture | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _thread: threading.Thread | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _latest_frame: CameraFrame | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _error: Exception | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            capture = self.capture_factory(camera_address(self.camera.source))
            if not capture.isOpened():
                capture.release()
                raise RuntimeError(
                    f"Could not open camera: {self.camera.id}"
                )

            self._capture = capture
            self._shutdown.clear()
            self._enabled.clear()
            with self._frame_lock:
                self._latest_frame = None
                self._error = None

            thread = threading.Thread(
                target=self._run,
                daemon=False,
                name=f"gerbera-camera-{self.camera.id}",
            )
            self._thread = thread
            thread.start()

    def enable(self) -> None:
        with self._lifecycle_lock:
            self._require_running()
            with self._frame_lock:
                self._error = None
            self._enabled.set()

    def disable(self) -> None:
        self._enabled.clear()

    @property
    def is_enabled(self) -> bool:
        return self._enabled.is_set() and not self._shutdown.is_set()

    def get_latest_frame(self) -> CameraFrame | None:
        with self._frame_lock:
            error = self._error
            frame = self._latest_frame

        if error is not None:
            raise RuntimeError(
                f"Camera capture failed: {self.camera.id}"
            ) from error
        return frame

    def close(self, timeout: float = 2.0) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            capture = self._capture
            if thread is None:
                if capture is not None:
                    capture.release()
                    self._capture = None
                return

            self._shutdown.set()
            self._enabled.set()
            if capture is not None:
                capture.release()

        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError(
                f"Camera worker did not stop: {self.camera.id}"
            )

        with self._lifecycle_lock:
            self._thread = None
            self._capture = None
            self._enabled.clear()

    def _require_running(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            raise RuntimeError(
                f"Camera session is not running: {self.camera.id}"
            )

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._enabled.wait()
            if self._shutdown.is_set():
                return

            capture = self._capture
            if capture is None:
                return

            try:
                success, frame = capture.read()
            except Exception as exc:
                if self._shutdown.is_set():
                    return
                with self._frame_lock:
                    self._error = exc
                self._enabled.clear()
                continue

            if not success:
                if self._shutdown.is_set():
                    return
                with self._frame_lock:
                    self._error = RuntimeError("Could not read camera frame")
                self._enabled.clear()
                continue

            with self._frame_lock:
                self._latest_frame = frame


SessionFactory = Callable[[Camera], CameraSession]

@dataclass
class CameraRuntime:
    hardware_system: HardwareSystem
    session_factory: SessionFactory = field(
        default=CameraSession,
        repr=False,
    )
    sessions: dict[str, CameraSession] = field(default_factory=dict)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def start(self) -> None:
        try:
            with self._lock:
                for camera in self.hardware_system.cameras:
                    if camera.id in self.sessions:
                        continue

                    session = self.session_factory(camera)
                    session.start()
                    self.sessions[camera.id] = session
        except Exception as exc:
            self.close()
            raise RuntimeError("Could not start camera runtime") from exc

    def start_stream(self, camera_id: str) -> None:
        self.get_session(camera_id).enable()

    def stop_stream(self, camera_id: str) -> None:
        self.get_session(camera_id).disable()

    def get_latest_frame(self, camera_id: str) -> CameraFrame | None:
        return self.get_session(camera_id).get_latest_frame()

    def get_session(self, camera_id: str) -> CameraSession:
        with self._lock:
            session = self.sessions.get(camera_id)

        if session is None:
            raise RuntimeError(f"Camera does not exist: {camera_id}")
        return session

    def close(self) -> None:
        with self._lock:
            sessions = list(self.sessions.items())

        first_error: Exception | None = None
        for camera_id, session in sessions:
            try:
                session.close()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                with self._lock:
                    if self.sessions.get(camera_id) is session:
                        self.sessions.pop(camera_id)

        if first_error is not None:
            raise RuntimeError("Could not stop camera runtime") from first_error
