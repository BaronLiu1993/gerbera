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
    stop_event: threading.Event | None = None
    thread: threading.Thread | None = None
    first_frame_ready: threading.Event = field(default_factory=threading.Event)
    startup_error: Exception | None = None


@dataclass
class CameraRuntime:
    hardware_system: HardwareSystem
    startup_timeout_seconds: float = 5.0
    camera_registry: dict[str, CameraSession] = field(default_factory=dict)
    latest_frames: dict[str, Frame | None] = field(default_factory=dict)
    lock: threading.RLock = field(
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

    @staticmethod
    def capture_frame(capture, camera_key: str) -> Frame:
        success, frame = capture.read()
        if not success:
            raise RuntimeError(f"Could not read camera frame: {camera_key}")

        return Frame(
            image=frame,
            timestamp=datetime.datetime.now(),
        )

    def build_camera_sessions(self) -> list[str]:
        camera_keys: list[str] = []
        for camera in self.hardware_system.cameras:
            if camera.camera_id not in self.camera_registry:
                self.camera_registry[camera.camera_id] = CameraSession(camera=camera)
                self.latest_frames[camera.camera_id] = None
            camera_keys.append(camera.camera_id)
        return camera_keys

    def start(self) -> None:
        with self.lock:
            camera_keys = self.build_camera_sessions()

        started_camera_keys: list[str] = []
        try:
            for camera_key in camera_keys:
                self.turn_on_camera_stream(camera_key)
                started_camera_keys.append(camera_key)
            for camera_key in started_camera_keys:
                self.wait_for_first_frame(camera_key)
        except Exception:
            for camera_key in started_camera_keys:
                self.turn_off_camera_stream(camera_key)
            raise

    def wait_for_first_frame(self, camera_key: str) -> None:
        camera_session = self.get_camera_session(camera_key)
        if not camera_session.first_frame_ready.wait(
            timeout=self.startup_timeout_seconds
        ):
            raise TimeoutError(
                f"Camera did not capture a frame within "
                f"{self.startup_timeout_seconds} seconds: {camera_key}"
            )

        with self.lock:
            startup_error = camera_session.startup_error
            latest_frame = self.latest_frames[camera_key]
        if startup_error is not None:
            raise RuntimeError(
                f"Camera failed before capturing its first frame: {camera_key}"
            ) from startup_error
        if latest_frame is None:
            raise RuntimeError(
                f"Camera reported readiness without a frame: {camera_key}"
            )

    def get_camera_session(self, camera_key: str) -> CameraSession:
        with self.lock:
            camera_session = self.camera_registry.get(camera_key)
            if camera_session is None:
                raise RuntimeError("Camera does not exist")

            return camera_session

    # get discrete frames
    def capture_frames(
        self,
        camera_key: str,
        image_count: int = 1,
        interval_seconds: float = 0.0,
    ) -> list[Frame]:
        frames: list[Frame] = []
        if image_count < 1:
            raise ValueError("image_count must be at least 1")

        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")

        camera_session = self.get_camera_session(camera_key)
        camera_address = self.get_camera_address(camera_session.camera.source)
        capture = cv2.VideoCapture(camera_address)
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Could not open camera: {camera_key}")

            for image_index in range(image_count):
                frames.append(self.capture_frame(capture, camera_key))
                if interval_seconds > 0 and image_index < image_count - 1:
                    time.sleep(interval_seconds)

            return frames
        finally:
            capture.release()

    def capture_loop(self, camera_key: str) -> None:
        camera_session = self.get_camera_session(camera_key)
        camera = camera_session.camera
        stop_event = camera_session.stop_event
        if stop_event is None:
            raise RuntimeError(f"Camera is not running: {camera_key}")

        camera_address = self.get_camera_address(camera.source)
        capture = None
        try:
            capture = cv2.VideoCapture(camera_address)
            if not capture.isOpened():
                raise RuntimeError(f"Could not open camera: {camera_key}")

            while not stop_event.is_set():
                latest_frame = self.capture_frame(capture, camera_key)
                with self.lock:
                    self.latest_frames[camera.camera_id] = latest_frame
                    camera_session.first_frame_ready.set()
        except Exception as exc:
            with self.lock:
                captured_frame = (
                    self.latest_frames[camera.camera_id] is not None
                )
                camera_session.startup_error = exc
                camera_session.first_frame_ready.set()
            if captured_frame:
                raise
        finally:
            if capture is not None:
                capture.release()

    def get_latest_frame(self, camera_key: str) -> Frame:
        self.get_camera_session(camera_key)
        with self.lock:
            latest_frame = self.latest_frames[camera_key]
        if latest_frame is None:
            raise RuntimeError(
                f"Camera has not captured a frame yet: {camera_key}"
            )
        return latest_frame

    def turn_on_camera_stream(
        self,
        camera_key: str,
    ) -> None:
        camera_session = self.get_camera_session(camera_key)
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self.capture_loop,
            args=(camera_key,),
            name=f"camera.{camera_key}",
            daemon=False,
        )

        with self.lock:
            if camera_session.thread is not None:
                raise RuntimeError(f"Camera is already running: {camera_key}")
            camera_session.first_frame_ready.clear()
            camera_session.startup_error = None
            camera_session.stop_event = stop_event
            camera_session.thread = thread
            try:
                thread.start()
            except RuntimeError as exc:
                camera_session.stop_event = None
                camera_session.thread = None
                raise RuntimeError(
                    f"Could Not Start Camera Thread {camera_key}"
                ) from exc

    def turn_off_camera_stream(self, camera_key: str) -> None:
        camera_session = self.get_camera_session(camera_key)
        with self.lock:
            stop_event = camera_session.stop_event
            thread = camera_session.thread

        if stop_event is None or thread is None:
            raise RuntimeError(f"Camera is not running: {camera_key}")

        stop_event.set()
        thread.join(timeout=5.0)
        if thread.is_alive():
            raise RuntimeError(f"Camera stream did not stop: {camera_key}")

        with self.lock:
            camera_session.stop_event = None
            camera_session.thread = None

    def close(self) -> None:
        with self.lock:
            camera_keys = [
                camera_key
                for camera_key, camera_session in self.camera_registry.items()
                if camera_session.thread is not None
            ]

        first_error: RuntimeError | None = None
        for camera_key in camera_keys:
            try:
                self.turn_off_camera_stream(camera_key)
            except RuntimeError as exc:
                if first_error is None:
                    first_error = exc

        if first_error is not None:
            raise RuntimeError("Could not clean up cameras") from first_error

        with self.lock:
            self.camera_registry.clear()
            self.latest_frames.clear()
