from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.environment_runtime import EnvironmentRuntime
from gerbera_sdk.models.runtime.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.movement_runtime import MovementRuntime


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    event_worker: EventWorker
    environment_runtime: EnvironmentRuntime
    event_listener: EventListener
    event_bus: EventBus
    hardware_runtime: HardwareRuntime
    movement_runtime: MovementRuntime | None = None

    @asynccontextmanager
    async def __call__(
        self,
        server: FastMCP,
    ) -> AsyncGenerator[dict[str, object], None]:
        with self._start_resources():
            yield {
                "board_runtime": self.board_runtime,
                "camera_runtime": self.camera_runtime,
                "event_worker": self.event_worker,
                "environment_runtime": self.environment_runtime,
                "hardware_runtime": self.hardware_runtime,
                "movement_runtime": self.movement_runtime,
            }

    def _start_resources(
        self,
    ) -> ExitStack:
        cleanup = ExitStack()
        try:
            self.board_runtime.start()
            cleanup.callback(self.board_runtime.close)

            if self.movement_runtime is not None:
                self.movement_runtime.reset_motors_to_standard_position()

            self.camera_runtime.start_cameras()
            cleanup.callback(self.camera_runtime.clean_up_cameras)

            self.event_worker.start()
            cleanup.callback(self.event_worker.stop)
            cleanup.callback(self.event_worker.wait_until_idle)
            cleanup.callback(self.event_bus.flush_event_buffers)

            self.event_listener.create_listeners()
            cleanup.callback(self.event_listener.stop_listeners)

            self.environment_runtime.turn_on_all_models()
            cleanup.callback(self.environment_runtime.turn_off_all_models)
        except Exception:
            cleanup.close()
            raise

        return cleanup
