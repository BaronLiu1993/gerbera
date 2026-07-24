from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, create_model

from gerbera_sdk.contracts.command_contract import (
    CommandSpec,
    ParameterSpec,
    ParameterType,
)
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

_PARAMETER_TYPES: dict[ParameterType, type] = {
    ParameterType.STRING: str,
    ParameterType.INT: int,
    ParameterType.FLOAT: float,
    ParameterType.BOOL: bool,
}


@dataclass
class ServerRuntime:
    hardware_system: HardwareSystem
    board_runtime: BoardRuntime
    event_bus: EventBus
    stream_controller: StreamController
    event_worker: EventWorker
    app: FastMCP
    event_listener: EventListener | None = None

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

        event = Event(
            event_type="STREAM",
            microcontroller_id=microcontroller.id,
            event_name=connection.event_name,
            streamable=True,
            table_name=connection.event_name,
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
            raise RuntimeError("Event listener is already running")

        event_listener = EventListener(
            hardware_system=self.hardware_system,
            _serial_pool=self.board_runtime.serial_pool,
            _threads={},
            _event_bus=self.event_bus,
        )
        event_listener.create_listeners()
        self.event_listener = event_listener

    def _stop_event_listener(self) -> None:
        if self.event_listener is None:
            raise RuntimeError("Event listener is not running")

        self.event_listener.stop_listeners()
        self.event_listener = None

    def _send_connection_command(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        action: str,
        params: dict[str, str] | None = None,
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

        serial_connection.write(built_command)
        return event.wait_for_response()

    def _register_connection_action(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()

        def action_function(
            params: dict[str, str] | None = None,
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
        command: CommandSpec,
    ) -> Callable[..., dict[str, str]]:
        action = command.method.strip().upper()
        if not command.params:

            def tool_function() -> dict[str, str]:
                return connection.perform_action(action)

            return tool_function

        params_model = self._build_tool_params_model(
            connection,
            command,
        )

        def tool_function(params: BaseModel) -> dict[str, str]:
            values = params.model_dump(exclude_none=True)
            serialized = {
                name: str(value)
                for name, value in values.items()
            }
            return connection.perform_action(action, serialized)

        tool_function.__annotations__["params"] = params_model
        return tool_function

    def _build_tool_params_model(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        for name, parameter in command.params.items():
            annotation = self._build_parameter_annotation(parameter)
            default = ... if parameter.required else None
            if not parameter.required:
                annotation |= None
            fields[name] = (annotation, default)

        model_name = (
            f"{connection.name.title().replace('_', '')}"
            f"{command.method.title()}Params"
        )

        return create_model(
            model_name,
            __config__=ConfigDict(extra="forbid"),
            **fields,
        )

    def _build_parameter_annotation(
        self,
        parameter: ParameterSpec,
    ) -> Any:
        value_type: Any = _PARAMETER_TYPES[parameter.type]
        if parameter.enum:
            value_type = Literal.__getitem__(tuple(parameter.enum))

        return Annotated[
            value_type,
            Field(
                description=parameter.description or None,
                ge=parameter.min,
                le=parameter.max,
            ),
        ]

    def _build_stream_toggle_tool_function(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        state: str,
    ) -> Callable[[], dict[str, str]]:
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
    ) -> Callable[[], dict[str, str]]:
        def tool_function() -> dict[str, str]:
            return connection.perform_action("WRITE", {"state": state})

        return tool_function

    def _register_connection_tool(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> None:
        description = command.description.strip()
        if not description:
            raise ValueError(
                f"Command description is required: "
                f"{command.method},{connection.name}"
            )

        action = command.method.strip().lower()
        tool_name = f"{action}_{connection.name}"
        tool_function = self._build_tool_function(
            connection,
            command,
        )
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
        )

    def _register_tool(
        self,
        name: str,
        description: str,
        tool_function: Callable[..., dict[str, str]],
    ) -> None:
        tool_function.__name__ = name
        tool_function.__doc__ = description
        self.app.tool(name=name, description=description)(tool_function)

    def _register_state_toggle_tool(
        self,
        connection: Connection,
        state: str,
        tool_name: str,
        description: str,
    ) -> None:
        tool_function = self._build_state_toggle_tool_function(connection, state)
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
        )

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
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
        )

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
