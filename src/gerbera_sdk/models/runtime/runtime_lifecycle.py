from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from fastmcp import FastMCP

from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime


class StreamController(Protocol):
    def flush_all(self) -> None: ...


class ServerRuntime(Protocol):
    stream_controller: StreamController

    def _start_event_listener(self) -> None: ...

    def _stop_event_listener(self) -> None: ...


@dataclass
class RuntimeLifecycle:
    board_runtime: BoardRuntime
    camera_runtime: CameraRuntime
    database_runtime: DatabaseRuntime
    server_runtime: ServerRuntime | None = None

    def bind_server_runtime(self, server_runtime: ServerRuntime) -> None:
        if self.server_runtime is not None:
            raise RuntimeError("Server runtime is already bound")
        self.server_runtime = server_runtime

    @asynccontextmanager
    async def __call__(
        self,
        server: FastMCP,
    ) -> AsyncIterator[dict[str, object]]:
        server_runtime = self.server_runtime
        if server_runtime is None:
            raise RuntimeError("Server runtime is not bound")

        with self._start_resources(server_runtime):
            yield {
                "board_runtime": self.board_runtime,
                "camera_runtime": self.camera_runtime,
                "database_runtime": self.database_runtime,
            }

    def _start_resources(
        self,
        server_runtime: ServerRuntime,
    ) -> ExitStack:
        cleanup = ExitStack()
        try:
            self.board_runtime.start()
            cleanup.callback(self.board_runtime.close)

            self.camera_runtime.start()
            cleanup.callback(self.camera_runtime.close)

            self.database_runtime.start()
            cleanup.callback(self.database_runtime.stop)
            cleanup.callback(server_runtime.stream_controller.flush_all)

            server_runtime._start_event_listener()
            cleanup.callback(server_runtime._stop_event_listener)
        except Exception:
            cleanup.close()
            raise

        return cleanup
