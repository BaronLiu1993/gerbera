from dataclasses import dataclass, field
from datetime import datetime
import threading
import cv2
from gerbera_sdk.models.hardware.camera import Camera, Frame
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class CameraSession:
    camera: Camera
    stop_event: threading.Event
    thread: threading.Thread
    latest_frame: Frame | None = None


@dataclass
class CameraRuntime:
    hardware_system: HardwareSystem
    sessions: dict[str, CameraSession] = field(
        init=False,
        default_factory=dict,
    )

    def initialise_camera_sessions(self) -> None:
        if self.sessions:
            return

        for camera in self.hardware_system.cameras:
            if camera.camera_id in self.sessions:
                raise ValueError(f"Duplicate camera ID: {camera.camera_id}")

            self.sessions[camera.camera_id] = CameraSession(
                camera=camera,
                stop_event=threading.Event(),
                thread=threading.Thread(
                    target=self.capture_loop,
                    args=(camera.camera_id,),
                    name=f"camera.{camera.camera_id}",
                    daemon=False,
                ),
            )

        for camera_id in self.sessions:
            session = self.get_camera_session(camera_id)
            try:
                if session.thread.is_alive():
                    raise RuntimeError(f"Camera is already running: {camera_id}")
                session.thread.start()
            except Exception:
                self.close_camera_sessions()
                break

    def close_camera_sessions(self) -> None:
        for camera_id in self.sessions:
            session = self.get_camera_session(camera_id)
            session.stop_event.set()
            session.thread.join(timeout=5.0)


    def get_camera_session(self, camera_id: str) -> CameraSession:
        try:
            return self.sessions[camera_id]
        except KeyError as error:
            raise RuntimeError(f"Camera does not exist: {camera_id}") from error

    def get_latest_frame(self, camera_id: str) -> Frame:
        latest_frame = self.get_camera_session(camera_id).latest_frame
        if latest_frame is None:
            raise RuntimeError(f"Camera has not captured a frame yet: {camera_id}")
        return latest_frame

    def capture_loop(self, camera_id: str) -> None:
        session = self.get_camera_session(camera_id)
        capture = cv2.VideoCapture(session.camera.camera_source)
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Could not open camera: {camera_id}")

            while not session.stop_event.is_set():
                success, image = capture.read()
                if not success:
                    raise RuntimeError(f"Could not read camera frame: {camera_id}")
                session.latest_frame = Frame(image=image, timestamp=datetime.now())
        finally:
            capture.release()
