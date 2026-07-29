from dataclasses import dataclass, field
import threading
from typing import Protocol

import cv2

from gerbera_sdk.models.hardware.camera import (
    CameraSource,
    DeviceCameraSource,
    MJPEGSource,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


CameraAddress = int | str
CameraFrame = object

class VideoCapture(Protocol):
    def isOpened(self) -> bool: ...

    def read(self) -> tuple[bool, CameraFrame]: ...

    def release(self) -> None: ...


@dataclass
class CameraRuntime:
    hardware_system: HardwareSystem
    connection_pool: dict[str, VideoCapture] = field(default_factory=dict)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    @staticmethod
    def _get_camera_address(source: CameraSource) -> CameraAddress:
        if isinstance(source, DeviceCameraSource):
            return source.device_index
        if isinstance(source, MJPEGSource):
            return source.stream_url
        raise TypeError(f"Unsupported camera source: {type(source).__name__}")


    def start(self) -> None:
        try:
            with self._lock:
                for camera in self.hardware_system.cameras:
                    if camera.id not in self.connection_pool:
                        capture = cv2.VideoCapture(
                            CameraRuntime._get_camera_address(camera.source)
                        )
                        if not capture.isOpened():
                            capture.release()
                            raise RuntimeError(
                                f"Could not open camera: {camera.id}"
                            )

                        self.connection_pool[camera.id] = capture
        except Exception as exc:
            self.close()
            raise RuntimeError("Could not start camera runtime") from exc

    def capture_frame(self, camera_id: str) -> CameraFrame:
        with self._lock:
            capture = self.connection_pool.get(camera_id)
            if capture is None:
                raise RuntimeError(f"Camera does not exist: {camera_id}")

            success, frame = capture.read()

        if not success:
            raise RuntimeError(
                f"Could not read camera frame: {camera_id}"
            )
        return frame

    def close(self) -> None:
        with self._lock:
            connections = list(self.connection_pool.items())

        first_error: Exception | None = None
        for camera_id, capture in connections:
            try:
                capture.release()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                with self._lock:
                    if self.connection_pool.get(camera_id) is capture:
                        self.connection_pool.pop(camera_id)

        if first_error is not None:
            raise RuntimeError("Could not stop camera runtime") from first_error
