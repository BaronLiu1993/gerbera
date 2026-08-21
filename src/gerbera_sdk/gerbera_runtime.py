import os
import subprocess

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.environment_runtime import EnvironmentRuntime
from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime
from gerbera_sdk.models.runtime.hardware_runtime import HardwareRuntime


class GerberaRuntime:
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
        transport: str,
        database_host: str,
        database_port: int ,
        database_password: str,
        **transport_kwargs,
    ) -> None:
        GerberaRuntime.validate_unique_connection_names(hardware_system)

        database = GerberaRuntime.runtime_database(
            host=database_host,
            port=database_port,
            password=database_password,
        )
        board_runtime = BoardRuntime(hardware_system)
        camera_runtime = CameraRuntime(hardware_system)
        event_worker = EventWorker(database=database)
        environment_runtime = EnvironmentRuntime(hardware_system)
        hardware_runtime = HardwareRuntime()
        GerberaRuntime.register_connection_states(
            hardware_system=hardware_system,
            hardware_runtime=hardware_runtime,
        )

        event_bus = EventBus()
        reaction_bus = ReactionBus()
        event_listener = EventListener(
            hardware_system=hardware_system,
            serial_pool=board_runtime.serial_pool,
            event_bus=event_bus,
            reaction_bus=reaction_bus,
            hardware_runtime=hardware_runtime,
        )
        runtime_lifecycle = RuntimeLifecycle(
            board_runtime=board_runtime,
            camera_runtime=camera_runtime,
            event_worker=event_worker,
            environment_runtime=environment_runtime,
            event_listener=event_listener,
            event_bus=event_bus,
            hardware_runtime=hardware_runtime,
        )
        app = FastMCP(
            hardware_system.description,
            lifespan=runtime_lifecycle,
        )
        server_runtime = ServerRuntime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_bus=event_bus,
            event_worker=event_worker,
            app=app,
            camera_runtime=camera_runtime,
            environment_runtime=environment_runtime,
            event_listener=event_listener,
            reaction_bus=reaction_bus,
            hardware_runtime=hardware_runtime,
        )

        server_runtime.register_events()
        server_runtime.register_tools()
        app.run(transport=transport, **transport_kwargs)

    @staticmethod
    def validate_unique_connection_names(
        hardware_system: HardwareSystem,
    ) -> None:
        connection_owners: dict[str, str] = {}

        for microcontroller in hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                normalized_name = connection.name.strip().lower()
                if not normalized_name:
                    raise ValueError("Connection name cannot be empty")

                existing_owner = connection_owners.get(normalized_name)
                if existing_owner is not None:
                    raise ValueError(
                        f"Connection name must be globally unique: "
                        f"{connection.name}. Used by microcontrollers "
                        f"{existing_owner} and {microcontroller.id}"
                    )

                connection_owners[normalized_name] = microcontroller.id

    @staticmethod
    def register_connection_states(
        hardware_system: HardwareSystem,
        hardware_runtime: HardwareRuntime,
    ) -> None:
        for microcontroller in hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                for key in CommandCompiler.state_keys(connection):
                    hardware_runtime.register_state_store(key)

    # Change the database layer after
    @staticmethod
    def runtime_database(
        host: str,
        port: int,
        password: str,
    ) -> Database:
        return Database(
            host=host, 
            port=port,
            password=password,
            user="gerbera_writer",
            database_name="gerbera"
        )

    @staticmethod
    def install_dependencies(hardware_system: HardwareSystem) -> None:
        for package_name in hardware_system._get_required_microcontroller_libraries():
            subprocess.run(
                ["arduino-cli", "core", "install", package_name],
                check=True,
            )

        installed_libraries: set[str] = set()
        for microcontroller in hardware_system.microcontrollers:
            for library in microcontroller._get_required_connection_libraries():
                install_name = library.install.strip()
                normalized_name = install_name.lower()
                if not install_name or normalized_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_name)
