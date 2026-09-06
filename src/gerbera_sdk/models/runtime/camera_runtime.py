from dataclasses import dataclass, field
import datetime
import threading
import time

import cv2

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.models.hardware.camera import (
    CameraSource,
    DeviceCameraSource,
    MJPEGSource,
    Camera,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class CameraSession:
    camera: Camera
    _stop_event: threading.Event | None = None
    _thread: threading.Thread | None = None


@dataclass
class CameraRuntime:
    hardware_system: HardwareSystem
    camera_registry: dict[str, CameraSession] = field(default_factory=dict)
    frame_storage: dict[str, Frame | None] = field(default_factory=dict)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    # Factory Method that routes to the different sources available
    @staticmethod
    def get_camera_address(source: CameraSource) -> int | str:
        if isinstance(source, DeviceCameraSource):
            return source.device_index
        if isinstance(source, MJPEGSource):
            return source.stream_url
        raise TypeError(f"Unsupported camera source: {type(source).__name__}")

    def register_cameras(self) -> None:
        for camera in self.hardware_system.cameras:
            if camera.camera_id not in self.camera_registry:
                self.camera_registry[camera.camera_id] = CameraSession(camera=camera)
                self.frame_storage[camera.camera_id] = None

    def start_cameras(self) -> None:
        try:
            camera_keys = list(self.camera_registry)
            for camera_key in camera_keys:
                self.turn_on_camera_stream(camera_key)
        except Exception as exc:
            self.turn_off_camera_stream()
            raise ValueError(f"Failed to Start Cameras {exc}")

    def get_camera_session(self, camera_key: str) -> CameraSession:
        camera_session = self.camera_registry.get(camera_key)

        if camera_session is None:
            raise RuntimeError("Camera does not exist")

        return camera_session

    # get dicrete frames
    def capture_frames(
        self,
        camera_key: str,
        image_count: int = 1,
        interval_seconds: float = 0.0,
    ) -> list[Frame]:
        if image_count < 1:
            raise ValueError("image_count must be at least 1")

        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")

        camera_session = self.get_camera_session(camera_key)
        frames: list[Frame] = []

        for image_index in range(image_count):
            with self._lock:
                if camera_session._thread is None:
                    raise RuntimeError(f"Camera is not running: {camera_key}")

                latest_frame = camera_session.camera.latest_frame

            if latest_frame is None:
                raise RuntimeError(f"Camera has not captured a frame yet: {camera_key}")

            frames.append(latest_frame)
            if interval_seconds > 0 and image_index < image_count - 1:
                time.sleep(interval_seconds)

        return frames

    def capture_loop(self, camera_key: str) -> None:
        camera_session = self.get_camera_session(camera_key)
        camera = camera_session.camera
        stop_event = camera_session._stop_event
        if stop_event is None:
            raise RuntimeError(f"Camera is not running: {camera_key}")

        camera_address = self.get_camera_address(camera.source)
        capture = cv2.VideoCapture(camera_address)
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Could not open camera: {camera_key}")

            while not stop_event.is_set():
                success, frame = capture.read()
                if not success:
                    raise RuntimeError(f"Could not read camera frame: {camera_key}")

                latest_frame = Frame(
                    image=frame,
                    timestamp=datetime.datetime.now(),
                )

                with self._lock:
                    self.frame_storage[camera.camera_id] = latest_frame

        finally:
            capture.release()

    def turn_on_camera_stream(
        self,
        camera_key: str,
    ) -> None:
        camera_session = self.get_camera_session(camera_key)
        if camera_session._thread is not None:
            raise RuntimeError(f"Camera is already running: {camera_key}")

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self.capture_loop,
            args=(camera_key,),
            name=f"camera.{camera_key}",
            daemon=False,
        )
        camera_session._stop_event = stop_event
        camera_session._thread = thread

        try:
            thread.start()
        except RuntimeError as exc:
            with self._lock:
                camera_session._stop_event = None
                camera_session._thread = None
            raise RuntimeError(f"Could Not Start Camera Thread {camera_key}") from exc

    def turn_off_camera_stream(self, camera_key: str) -> None:
        camera_session = self.get_camera_session(camera_key)
        with self._lock:
            stop_event = camera_session._stop_event
            thread = camera_session._thread

        if stop_event is None or thread is None:
            raise RuntimeError(f"Camera is not running: {camera_key}")

        stop_event.set()
        thread.join(timeout=5.0)

        with self._lock:
            camera_session._stop_event = None
            camera_session._thread = None
