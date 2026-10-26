from dataclasses import dataclass

from gerbera_protocol import ReadinessReport
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker


@dataclass
class RuntimeReadiness:
    boards: BoardRuntime
    cameras: CameraRuntime
    models: ModelRuntime
    listener: EventListener
    worker: EventWorker
    phase: str = "starting"

    def snapshot(self) -> ReadinessReport:
        reasons = []
        if self.phase != "ready":
            reasons.append(f"SDK is {self.phase}")
        health = self.listener.get_health()
        with self.boards.lock:
            for board in self.boards.hardware_plan.boards:
                session = self.boards.sessions.get(board.microcontroller_id)
                if session is None or not session.heartbeat_thread.is_alive():
                    reasons.append(f"Board session unavailable: {board.microcontroller_id}")
                if health.get(board.microcontroller_id, {}).get("status") != "running":
                    reasons.append(f"Board listener unavailable: {board.microcontroller_id}")
        with self.cameras.lock:
            for camera in self.cameras.hardware_system.cameras:
                session = self.cameras.camera_registry.get(camera.camera_id)
                if (session is None or session.thread is None
                        or not session.thread.is_alive() or session.startup_error is not None):
                    reasons.append(f"Camera unavailable: {camera.camera_id}")
        with self.models.lock:
            if self.models.model_stream_failures or any(
                not stream.thread.is_alive() for stream in self.models.model_streams.values()
            ):
                reasons.append("Required inference streams failed")
        if self.worker.thread is None or not self.worker.thread.is_alive() or self.worker.failures:
            reasons.append("Device event storage worker unavailable")
        return ReadinessReport(
            service="sdk",
            phase=self.phase if self.phase != "ready" else ("degraded" if reasons else "ready"),
            reasons=tuple(reasons), instance_id=self.boards.hardware_plan.hardware_system_id,
        )
