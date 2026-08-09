from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    event_worker: EventWorker
    model_runtime: ModelRuntime
    event_listener: EventListener
    event_bus: EventBus

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
                "model_runtime": self.model_runtime,
            }

    def _start_resources(
        self,
    ) -> ExitStack:
        cleanup = ExitStack()
        try:
            self.board_runtime.start()
            cleanup.callback(self.board_runtime.close)

            self.camera_runtime.start_cameras()
            cleanup.callback(self.camera_runtime.clean_up_cameras)

            self.event_worker.start()
            cleanup.callback(self.event_worker.stop)
            cleanup.callback(self.event_worker.wait_until_idle)
            cleanup.callback(self.event_bus.flush_event_buffers)

            cleanup.callback(self.event_listener.stop_listeners)
            self.event_listener.create_listeners()

            self.model_runtime.turn_on_all_models()
            cleanup.callback(self.model_runtime.turn_off_all_models)
        except Exception:
            cleanup.close()
            raise

        return cleanup
