import subprocess

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.rules.rule_buffer import RuleBuffer
from gerbera_sdk.events.rules.rule_bus import RuleBus
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


class GerberaRuntime:
    @staticmethod
    def setup(
        hardware_system: HardwareSystem,
        install_dependencies: bool = True,
        flash_firmware: bool = True,
    ) -> None:
        if install_dependencies:
            GerberaRuntime._install_dependencies(hardware_system)

        if flash_firmware:
            Flash.flash(hardware_system)

    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str = "stdio",
        mcp_url: str = "",
        **transport_kwargs,
    ) -> None:
        GerberaRuntime._validate_unique_connection_names(hardware_system)

        board_runtime = BoardRuntime(hardware_system)
        camera_runtime = CameraRuntime(hardware_system)
        event_worker = EventWorker()
        database_runtime = DatabaseRuntime(hardware_system, event_worker)
        model_runtime = ModelRuntime(hardware_system)

        event_bus = EventBus()
        stream_controller = StreamController(event_bus)
        rule_bus = RuleBus()
        rule_buffer = RuleBuffer(rule_bus)
        event_listener = EventListener(
            hardware_system=hardware_system,
            _serial_pool=board_runtime.serial_pool,
            _threads={},
            _event_bus=event_bus,
            _rule_buffer=rule_buffer,
        )
        agent_runtime = AgentRuntime(
            mcp_url=mcp_url,
            rule_bus=rule_bus,
            rule_buffer=rule_buffer,
            valid_event_keys=event_bus.events,
        )

        runtime_lifecycle = RuntimeLifecycle(
            board_runtime=board_runtime,
            camera_runtime=camera_runtime,
            database_runtime=database_runtime,
            model_runtime=model_runtime,
            event_listener=event_listener,
            stream_controller=stream_controller,
        )
        app = FastMCP(
            hardware_system.description,
            lifespan=runtime_lifecycle,
        )
        server_runtime = ServerRuntime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_bus=event_bus,
            stream_controller=stream_controller,
            event_worker=event_worker,
            app=app,
            camera_runtime=camera_runtime,
            model_runtime=model_runtime,
            agent_runtime=agent_runtime,
            event_listener=event_listener,
            rule_bus=rule_bus,
            rule_buffer=rule_buffer,
        )

        server_runtime._register_events()
        server_runtime.register_tools()
        app.run(transport=transport, **transport_kwargs)

    @staticmethod
    def _validate_unique_connection_names(
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
    def _install_dependencies(hardware_system: HardwareSystem) -> None:
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
