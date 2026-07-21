import subprocess

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


class GerberaRuntime:
    @staticmethod
    def install_dependencies(hardware_system: HardwareSystem) -> None:
        for package_name in hardware_system.get_required_microcontroller_packages():
            subprocess.run(
                ["arduino-cli", "core", "install", package_name],
                check=True,
            )

        installed_libraries: set[str] = set()
        for microcontroller in hardware_system.microcontrollers:
            for library in microcontroller.get_required_libraries():
                install_name = library.install.strip()
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_install_name)

    @staticmethod
    def setup(
        hardware_system: HardwareSystem,
        install_dependencies: bool = True,
        flash_firmware: bool = True,
    ) -> None:
        if install_dependencies:
            GerberaRuntime.install_dependencies(hardware_system)

        if flash_firmware:
            Flash.flash(hardware_system)

    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str = "stdio",
        **transport_kwargs,
    ) -> None:
        board_runtime = GerberaRuntime._build_board_runtime(hardware_system)
        event_worker = GerberaRuntime._build_event_worker()
        database_runtime = GerberaRuntime._build_database_runtime(
            hardware_system,
            event_worker,
        )
        server_runtime = GerberaRuntime._build_server_runtime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_worker=event_worker,
        )

        try:
            board_runtime.start()
            database_runtime.start()
            server_runtime._register_events()
            GerberaRuntime._register_server_runtime_tools(server_runtime)
            server_runtime._start_event_listener()
            server_runtime.app.run(
                transport=transport,
                **transport_kwargs,
            )
        finally:
            server_runtime._stop_event_listener()
            server_runtime.stream_controller.flush_all()
            database_runtime.stop()
            board_runtime.close()

    @staticmethod
    def _build_board_runtime(
        hardware_system: HardwareSystem,
    ) -> BoardRuntime:
        return BoardRuntime(hardware_system=hardware_system)

    @staticmethod
    def _build_server_runtime(
        hardware_system: HardwareSystem,
        board_runtime: BoardRuntime,
        event_worker: EventWorker,
    ) -> ServerRuntime:
        event_bus = EventBus()
        stream_controller = StreamController(event_bus)
        app = FastMCP(hardware_system.description)

        return ServerRuntime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_bus=event_bus,
            stream_controller=stream_controller,
            event_worker=event_worker,
            app=app,
        )

    @staticmethod
    def _build_event_worker() -> EventWorker:
        return EventWorker()

    @staticmethod
    def _build_database_runtime(
        hardware_system: HardwareSystem,
        event_worker: EventWorker,
    ) -> DatabaseRuntime:
        return DatabaseRuntime(
            hardware_system=hardware_system,
            event_worker=event_worker,
        )

    @staticmethod
    def _connection_supports_state_toggle(connection: Connection) -> bool:
        for command in CommandCompiler.command_specs(connection):
            if command.method.strip().upper() != "WRITE":
                continue

            state_param = command.params.get("state")
            if state_param is None:
                continue

            return {"on", "off"}.issubset(set(state_param.enum))

        return False

    @staticmethod
    def _connection_supports_stream_toggle(connection: Connection) -> bool:
        return (
            connection.database is not None
            and GerberaRuntime._connection_supports_state_toggle(connection)
        )

    @staticmethod
    def _register_server_runtime_tools(server_runtime: ServerRuntime) -> None:
        for microcontroller in server_runtime.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                GerberaRuntime._register_connection_tools(
                    server_runtime=server_runtime,
                    microcontroller=microcontroller,
                    connection=connection,
                )

    @staticmethod
    def _register_connection_tools(
        server_runtime: ServerRuntime,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        for command in CommandCompiler.command_specs(connection):
            server_runtime._register_connection_action(
                microcontroller,
                connection,
                command,
            )
            server_runtime._register_connection_tool(connection, command)

        if GerberaRuntime._connection_supports_state_toggle(connection):
            server_runtime._register_state_toggle_tools(connection)

        if GerberaRuntime._connection_supports_stream_toggle(connection):
            server_runtime._register_stream_toggle_tools(
                microcontroller,
                connection,
            )
