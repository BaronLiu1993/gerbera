from dataclasses import dataclass, field
from typing import Optional

from fastmcp import FastMCP

from gerbera_sdk.contracts.command_contract import CommandSpec
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


@dataclass
class ServerRuntime:
    hardware_system: HardwareSystem
    board_runtime: BoardRuntime
    event_bus: EventBus 
    stream_controller: StreamController
    event_worker: EventWorker
    app: FastMCP
    event_listener: EventListener | None = field(default=None)

    def _register_mcp_event(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        event = Event(
            event_type="MCP",
            microcontroller_id=microcontroller.id,
            event_name=connection.event_name,
        )
        self.event_bus.add_event(
            "MCP",
            microcontroller.id,
            connection.event_name,
            event,
        )

    def _register_stream_event(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        if connection.database is None:
            return

        table_name = connection.event_name
        event = Event(
            event_type="STREAM",
            microcontroller_id=microcontroller.id,
            event_name=connection.event_name,
            streamable=True,
            table_name=table_name,
            event_worker=self.event_worker,
        )
        self.event_bus.add_event(
            "STREAM",
            microcontroller.id,
            connection.event_name,
            event,
        )

    def _register_events(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                self._register_mcp_event(microcontroller, connection)
                self._register_stream_event(microcontroller, connection)

    def _start_event_listener(self) -> None:
        if self.event_listener is not None:
            return

        self.event_listener = EventListener(
            hardware_system=self.hardware_system,
            _serial_pool=self.board_runtime.serial_pool,
            _threads={},
            _event_bus=self.event_bus,
        )
        self.event_listener.create_listeners()

    def _stop_event_listener(self) -> None:
        if self.event_listener is None:
            return

        self.event_listener.stop_listeners()
        self.event_listener = None

    def _send_connection_command(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        serial_connection = self.board_runtime.get_serial_connection(
            microcontroller
        )
        built_command = CommandCompiler.build_command(
            connection,
            action=action,
            params=params,
        )

        event = self.event_bus.get_handler(
            ("MCP", microcontroller.id, connection.event_name)
        )
        event.clear_responses()

        write = getattr(serial_connection, "write", None)
        if callable(write):
            write(built_command)
        else:
            response = serial_connection.send(built_command)
            if response:
                return CommandCompiler.parse_response(response)

        return event.wait_for_response()

    def _register_connection_action(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()

        def action_function(
            params: Optional[dict[str, str]] = None,
        ) -> dict[str, str]:
            return self._send_connection_command(
                microcontroller=microcontroller,
                connection=connection,
                action=action,
                params=params,
            )

        connection.register_action(action, action_function)

    def _build_tool_function(
        self,
        connection: Connection,
        action: str,
    ):
        def tool_function(
            params: Optional[dict[str, str]] = None,
        ) -> dict[str, str]:
            return connection.perform_action(action, params)

        return tool_function

    def _build_stream_toggle_tool_function(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        state: str,
    ):
        def tool_function() -> dict[str, str]:
            response = connection.perform_action("WRITE", {"state": state})

            if state == "off":
                self.stream_controller.stop_stream(
                    microcontroller,
                    connection,
                )

            return response

        return tool_function

    def _build_state_toggle_tool_function(
        self,
        connection: Connection,
        state: str,
    ):
        def tool_function() -> dict[str, str]:
            return connection.perform_action("WRITE", {"state": state})

        return tool_function

    def _register_connection_tool(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()
        tool_name = f"{action.lower()}_{connection.name}"
        tool_function = self._build_tool_function(connection, action)
        tool_function.__name__ = tool_name

        command_description = CommandCompiler.describe_command(connection, action)
        tool_function.__doc__ = connection.description or (
            f"Send {command_description} over serial."
        )

        self.app.tool(
            name=tool_name,
            description=tool_function.__doc__,
        )(tool_function)

    def _register_state_toggle_tool(
        self,
        connection: Connection,
        state: str,
        tool_name: str,
        description: str,
    ) -> None:
        tool_function = self._build_state_toggle_tool_function(connection, state)
        tool_function.__name__ = tool_name
        tool_function.__doc__ = description

        self.app.tool(
            name=tool_name,
            description=description,
        )(tool_function)

    def _register_state_toggle_tools(self, connection: Connection) -> None:
        self._register_state_toggle_tool(
            connection=connection,
            state="on",
            tool_name=f"turn_on_{connection.name}",
            description=f"Turn on {connection.name}.",
        )
        self._register_state_toggle_tool(
            connection=connection,
            state="off",
            tool_name=f"turn_off_{connection.name}",
            description=f"Turn off {connection.name}.",
        )

    def _register_stream_toggle_tool(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        state: str,
        tool_name: str,
        description: str,
    ) -> None:
        tool_function = self._build_stream_toggle_tool_function(
            microcontroller=microcontroller,
            connection=connection,
            state=state,
        )
        tool_function.__name__ = tool_name
        tool_function.__doc__ = description

        self.app.tool(
            name=tool_name,
            description=description,
        )(tool_function)

    def _register_stream_toggle_tools(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        self._register_stream_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state="on",
            tool_name=f"turn_on_{connection.name}_stream",
            description=f"Turn on continuous streaming for {connection.name}.",
        )
        self._register_stream_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state="off",
            tool_name=f"turn_off_{connection.name}_stream",
            description=f"Turn off continuous streaming for {connection.name}.",
        )

    def _register_tools(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                for command in CommandCompiler.command_specs(connection):
                    self._register_connection_action(
                        microcontroller,
                        connection,
                        command,
                    )
                    self._register_connection_tool(connection, command)

                self._register_state_toggle_tools(connection)
                self._register_stream_toggle_tools(microcontroller, connection)
