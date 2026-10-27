from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.movement.movement_runtime import MovementRuntime
from gerbera_sdk.firmware.firmware_verifier import FirmwareVerifier
from gerbera_sdk.models.runtime.server.readiness import RuntimeReadiness
from gerbera_sdk.models.runtime.storage.storage import RuntimeStorage


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    event_worker: EventWorker
    model_runtime: ModelRuntime
    event_listener: EventListener
    event_bus: EventBus
    hardware_runtime: HardwareRuntime
    movement_runtime: MovementRuntime | None = None
    storage: RuntimeStorage | None = None
    readiness: RuntimeReadiness | None = None

    @asynccontextmanager
    async def __call__(
        self,
        server: FastMCP,
    ) -> AsyncGenerator[dict[str, object], None]:
        try:
            with self.start_resources():
                if self.readiness is not None:
                    self.readiness.phase = "ready"
                try:
                    yield {
                        "board_runtime": self.board_runtime,
                        "camera_runtime": self.camera_runtime,
                        "event_worker": self.event_worker,
                        "model_runtime": self.model_runtime,
                        "hardware_runtime": self.hardware_runtime,
                        "movement_runtime": self.movement_runtime,
                    }
                finally:
                    if self.readiness is not None:
                        self.readiness.phase = "stopping"
        except BaseException:
            if self.readiness is not None:
                self.readiness.phase = "failed"
            raise

    def start_resources(
        self,
    ) -> ExitStack:
        startup_cleanup = ExitStack()
        try:
            if self.storage is not None:
                self.storage.prepare()
            FirmwareVerifier(self.board_runtime).verify()
            startup_cleanup.callback(self.board_runtime.close)
            self.board_runtime.start()

            startup_cleanup.callback(self.camera_runtime.close)
            self.camera_runtime.start()
            startup_cleanup.callback(
                self.model_runtime.turn_off_all_model_streams
            )
            self.model_runtime.turn_on_all_model_streams()

            startup_cleanup.callback(self.event_worker.stop)
            self.event_worker.start()
            startup_cleanup.callback(self.event_worker.wait_until_idle)
            startup_cleanup.callback(self.event_bus.flush_event_buffers)

            startup_cleanup.callback(self.event_listener.stop_listeners)
            self.event_listener.create_listeners()

            if self.movement_runtime is not None:
                self.movement_runtime.reset_motors_to_standard_position()

            startup_cleanup.pop_all()
        except BaseException:
            startup_cleanup.close()
            raise

        runtime_cleanup = ExitStack()
        runtime_cleanup.callback(self.board_runtime.close)
        runtime_cleanup.callback(self.event_worker.stop)
        runtime_cleanup.callback(self.event_worker.wait_until_idle)
        runtime_cleanup.callback(self.event_bus.flush_event_buffers)
        runtime_cleanup.callback(self.event_listener.stop_listeners)
        runtime_cleanup.callback(self.camera_runtime.close)
        runtime_cleanup.callback(self.model_runtime.turn_off_all_model_streams)
        return runtime_cleanup
