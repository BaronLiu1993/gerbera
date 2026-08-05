from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastmcp import FastMCP

from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    database_runtime: DatabaseRuntime
    model_runtime: ModelRuntime
    server_runtime: ServerRuntime | None = None

    def bind_server_runtime(self, server_runtime: ServerRuntime) -> None:
        if self.server_runtime is not None:
            raise RuntimeError("Server runtime is already bound")
        self.server_runtime = server_runtime

    @asynccontextmanager
    async def __call__(
        self,
        server: FastMCP,
    ) -> AsyncGenerator[dict[str, object], None]:
        server_runtime = self.server_runtime
        if server_runtime is None:
            raise RuntimeError("Server runtime is not bound")

        with self._start_resources(server_runtime):
            yield {
                "board_runtime": self.board_runtime,
                "camera_runtime": self.camera_runtime,
                "database_runtime": self.database_runtime,
                "model_runtime": self.model_runtime,
            }

    def _start_resources(
        self,
        server_runtime: ServerRuntime,
    ) -> ExitStack:
        cleanup = ExitStack()
        try:
            self.board_runtime.start()
            cleanup.callback(self.board_runtime.close)

            self.camera_runtime.start_cameras()
            cleanup.callback(self.camera_runtime.clean_up_cameras)

            self.database_runtime.start()
            cleanup.callback(self.database_runtime.stop)
            cleanup.callback(server_runtime.stream_controller.flush_all)

            server_runtime._start_event_listener()
            cleanup.callback(server_runtime._stop_event_listener)

            self.model_runtime.turn_on_all_models()
            cleanup.callback(self.model_runtime.turn_off_all_models)
        except Exception:
            cleanup.close()
            raise

        return cleanup
