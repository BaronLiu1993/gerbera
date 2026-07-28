import subprocess
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field, StrictFloat

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.rules import OperatorEnum, RuleTriggerModeEnum
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.server_runtime import (
    EventCatalog,
    ServerRuntime,
)


class GerberaRuntime:

    # Driver Code for Setting Up Hardware Connection
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

    # Driver Code for Setting Up Server Connection
    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str = "stdio",
        mcp_url: str = "",
        **transport_kwargs,
    ) -> None:
        GerberaRuntime._validate_unique_connection_names(hardware_system)
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
        server_runtime.agent_runtime = GerberaRuntime._build_agent_runtime(
            server_runtime=server_runtime,
            mcp_url=mcp_url,
        )
        event_listener_started = False

        try:
            board_runtime.start()
            database_runtime.start()
            server_runtime._register_events()
            GerberaRuntime._register_server_runtime_tools(server_runtime)
            GerberaRuntime._register_agent_runtime_tool(server_runtime)
            GerberaRuntime._register_event_catalog_tool(server_runtime)
            server_runtime._start_event_listener()
            event_listener_started = True
            server_runtime.app.run(
                transport=transport,
                **transport_kwargs,
            )
        finally:
            try:
                if event_listener_started:
                    server_runtime._stop_event_listener()
            finally:
                try:
                    try:
                        server_runtime.stream_controller.flush_all()
                    finally:
                        database_runtime.stop()
                finally:
                    board_runtime.close()

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
                        f"Connection name must be globally unique: {connection.name}. "
                        f"Used by microcontrollers {existing_owner} and "
                        f"{microcontroller.id}"
                    )

                connection_owners[normalized_name] = microcontroller.id

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
    def _build_agent_runtime(
        server_runtime: ServerRuntime,
        mcp_url: str,
    ) -> AgentRuntime:
        return AgentRuntime(
            mcp_url=mcp_url,
            rule_bus=server_runtime.rule_bus,
            rule_buffer=server_runtime.rule_buffer,
            valid_event_keys=server_runtime.event_bus.events,
        )

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
    def _register_agent_runtime_tool(
        server_runtime: ServerRuntime,
    ) -> None:
        agent_runtime = server_runtime.agent_runtime
        if agent_runtime is None:
            raise RuntimeError("Agent runtime is not configured")

        def insert_rule(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
            expected_value: Annotated[
                StrictFloat,
                Field(allow_inf_nan=False),
            ],
            operator: OperatorEnum,
            callback_body: str,
            trigger_mode: RuleTriggerModeEnum = RuleTriggerModeEnum.REPEAT,
        ) -> dict[str, str]:
            return agent_runtime.insert_rule(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
                expected_value=expected_value,
                operator=operator,
                callback_body=callback_body,
                trigger_mode=trigger_mode,
            )

        server_runtime._register_tool(
            name="insert_rule",
            description=(
                "Create and register a rule for a hardware event. "
                "callback_body must contain only the Python statements for "
                "async callback(mcp_url, value). The runtime imports httpx "
                "and fastmcp.Client, adds the fixed function definition, and "
                "binds the configured MCP URL and finite-float sensor value. "
                "The agent must use the mcp_url parameter and must not provide "
                "or hardcode an endpoint."
            ),
            tool_function=insert_rule,
        )

        def delete_rule(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
        ) -> dict[str, str]:
            return agent_runtime.delete_rule(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
            )

        server_runtime._register_tool(
            name="delete_rule",
            description=(
                "Delete the rule registered for a hardware event and remove "
                "its local callback script."
            ),
            tool_function=delete_rule,
        )

    @staticmethod
    def _register_event_catalog_tool(
        server_runtime: ServerRuntime,
    ) -> None:
        def list_rule_events() -> EventCatalog:
            return server_runtime.get_event_catalog()

        server_runtime._register_tool(
            name="list_rule_events",
            description=(
                "List the registered hardware events that can be used "
                "when creating rules."
            ),
            tool_function=list_rule_events,
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
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_install_name)
