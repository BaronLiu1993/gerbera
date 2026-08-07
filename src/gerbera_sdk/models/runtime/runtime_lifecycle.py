from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastmcp import FastMCP

from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.stream_controller import StreamController


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    database_runtime: DatabaseRuntime
    model_runtime: ModelRuntime
    event_listener: EventListener
    stream_controller: StreamController

    @asynccontextmanager
    async def __call__(
        self,
        server: FastMCP,
    ) -> AsyncGenerator[dict[str, object], None]:
        with self._start_resources():
            yield {
                "board_runtime": self.board_runtime,
                "camera_runtime": self.camera_runtime,
                "database_runtime": self.database_runtime,
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

            self.database_runtime.start()
            cleanup.callback(self.database_runtime.stop)
            cleanup.callback(self.stream_controller.flush_all)

            cleanup.callback(self.event_listener.stop_listeners)
            self.event_listener.create_listeners()

            self.model_runtime.turn_on_all_models()
            cleanup.callback(self.model_runtime.turn_off_all_models)
        except Exception:
            cleanup.close()
            raise

        return cleanup
