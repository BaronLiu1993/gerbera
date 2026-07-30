from dataclasses import dataclass, field
import threading
import datetime
import cv2

from gerbera_sdk.models.hardware.camera import (
    CameraSource,
    DeviceCameraSource,
    MJPEGSource,
    Camera,
    Frame,
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
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    @staticmethod
    def _get_camera_address(source: CameraSource) -> str:
        if isinstance(source, DeviceCameraSource):
            return source.device_index
        if isinstance(source, MJPEGSource):
            return source.stream_url
        raise TypeError(f"Unsupported camera source: {type(source).__name__}")


    def register_cameras(self) -> None:
        with self._lock:
            for camera in self.hardware_system.cameras:
                if camera.id not in self.camera_registry:
                    self.camera_registry[camera.id] = CameraSession(camera=camera)


    def clean_up_cameras(self) -> None:
        with self._lock:
            camera_sessions = list(self.camera_registry.items())

        first_error: Exception | None = None
        for camera_key, camera_session in camera_sessions:
            try:
                if camera_session._thread is not None:
                    self.turn_off_camera_stream(camera_key)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                with self._lock:
                    if self.camera_registry.get(camera_key) is camera_session:
                        self.camera_registry.pop(camera_key)

        if first_error is not None:
            raise RuntimeError("Could not clean up cameras") from first_error

    def get_camera_session(self, camera_key: str) -> Camera:
        with self._lock:
            camera_session = self.camera_registry.get(camera_key)

        if camera_session is None:
            raise RuntimeError("Camera Does Not Exist")

        return camera_session

    def _capture_loop(self, camera_key: str) -> None:
        camera = self.get_camera_session(camera_key).camera
        camera_address = self._get_camera_address(camera.source)
        capture = cv2.VideoCapture(camera_address)
        try:
            while not camera.stop_event.is_set():
                success, frame = capture.read()

                print(success, frame)
                latest_frame = Frame(image=frame, timestamp=datetime.datetime.now())

                print(latest_frame)
                with self._lock:
                    camera.latest_frame = latest_frame

        finally:
            capture.release()

    def turn_on_camera_stream(self, camera_key: str):
        camera_session = self.get_camera(camera_key)

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._capture_loop,
            args=(camera_key,),
            name=f"camera-{camera_key}",
            daemon=False,
        )

        camera_session._stop_event, camera_session._thread = stop_event, thread

        try:
            thread.start()
        except RuntimeError as exc:
            self.turn_off_camera_stream(camera_key)
            raise RuntimeError(f"Could Not Start Camera Thread {camera_key}") from exc

    def turn_off_camera_stream(self, camera_key: str):
        camera_session = self.get_camera_session(camera_key)

        stop_event = camera_session._stop_event
        thread = camera_session._thread

        if stop_event is None or thread is None:
            raise RuntimeError(
                f"Camera is not running: {camera_key}"
            )

        stop_event.set()
        thread.join(timeout=5.0)

        if thread.is_alive():
            raise RuntimeError(
                f"Camera thread did not stop: {camera_key}"
            )

        with self._lock:
            camera_session._stop_event = None
            camera_session._thread = None
