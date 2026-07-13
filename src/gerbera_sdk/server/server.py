from gerbera_sdk.contracts.command_contract import CommandSpec
from typing import Optional

from gerbera_sdk.server.commands import CommandCompiler
from gerbera_sdk.server.serial_connection import SerialConnection
from gerbera_sdk.models.hardware_system import HardwareSystem
from gerbera_sdk.models.microcontroller import Microcontroller
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.events.stream_controller import StreamController
from fastmcp import FastMCP

# Set all ids to be auto set to be uuidv4
class GerberaServer:
    def __init__(self, hardware_system: HardwareSystem) -> None:
        self.hardware_system = hardware_system
        self.serial_pool: dict[str, SerialConnection] = {}
        self.event_bus = EventBus()
        self.stream_controller = StreamController(self.event_bus)
        self.event_listener: EventListener | None = None
        self.app = FastMCP(hardware_system.description)
        self._register_event_bus()
        self._register_tools()

    def _get_serial_connection(
        self,
        microcontroller: Microcontroller,
    ) -> SerialConnection:
        if microcontroller.id not in self.serial_pool:
            raise RuntimeError("Microcontroller Does not Exist")
        return self.serial_pool[microcontroller.id]

    def _register_serial_connection(self) -> None:
        try:
            for microcontroller in self.hardware_system.microcontrollers:
                if microcontroller.id in self.serial_pool:
                    continue

                connection = SerialConnection()
                connection.connect(
                    port=microcontroller.port,
                    baud=microcontroller.baud_rate,
                )
                microcontroller_id = microcontroller.id
                self.serial_pool[microcontroller_id] = connection
        except Exception as e:
            raise RuntimeError(e)

    def _register_event_bus(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                connection.event_bus = self.event_bus
                connection.__post_init__()

    def _start_event_listener(self) -> None:
        if self.event_listener is not None:
            return

        self.event_listener = EventListener(
            hardware_system=self.hardware_system,
            _serial_pool=self.serial_pool,
            _threads={},
            _event_bus=self.event_bus,
        )
        self.event_listener.create_listeners()

    def _register_tools(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                for command in CommandCompiler.command_specs(connection):
                    self._register_connection_tool(
                        microcontroller,
                        connection,
                        command,
                    )
                self._register_state_toggle_tools(microcontroller, connection)
                self._register_stream_toggle_tools(microcontroller, connection)

    def _connection_supports_state_toggle(self, connection) -> bool:
        for command in CommandCompiler.command_specs(connection):
            if command.method.strip().upper() != "WRITE":
                continue

            state_param = command.params.get("state")
            if state_param is None:
                continue

            return {"on", "off"}.issubset(set(state_param.enum))

        return False

    def _connection_supports_stream_toggle(self, connection) -> bool:
        return connection.database is not None and self._connection_supports_state_toggle(connection)

    def _register_state_toggle_tools(
        self,
        microcontroller: Microcontroller,
        connection,
    ) -> None:
        if not self._connection_supports_state_toggle(connection):
            return

        self._register_state_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state="on",
            tool_name=f"turn_on_{connection.name}",
            description=f"Turn on {connection.name}.",
        )
        self._register_state_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state="off",
            tool_name=f"turn_off_{connection.name}",
            description=f"Turn off {connection.name}.",
        )

    def _register_state_toggle_tool(
        self,
        microcontroller: Microcontroller,
        connection,
        state: str,
        tool_name: str,
        description: str,
    ) -> None:
        tool_function = self._build_state_toggle_tool_function(
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
        connection,
    ) -> None:
        if not self._connection_supports_stream_toggle(connection):
            return

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

    def _register_stream_toggle_tool(
        self,
        microcontroller: Microcontroller,
        connection,
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

    def _register_connection_tool(
        self,
        microcontroller: Microcontroller,
        connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()
        tool_name = f"{action.lower()}_{connection.name}"
        tool_function = self._build_tool_function(
            microcontroller,
            connection,
            action,
        )
        tool_function.__name__ = tool_name

        command_description = CommandCompiler.describe_command(connection, action)
        tool_function.__doc__ = connection.description or (
            f"Send {command_description} over serial."
        )

        self.app.tool(
            name=tool_name,
            description=tool_function.__doc__,
        )(tool_function)

    def _build_tool_function(
        self,
        microcontroller: Microcontroller,
        connection,
        action: str,
    ):
        def tool_function(
            params: Optional[dict[str, str]] = None,
        ) -> dict[str, str]:
            return self._send_connection_command(
                microcontroller=microcontroller,
                connection=connection,
                action=action,
                params=params,
            )

        return tool_function

    def _build_stream_toggle_tool_function(
        self,
        microcontroller: Microcontroller,
        connection,
        state: str,
    ):
        def tool_function() -> dict[str, str]:
            response = self._send_connection_command(
                microcontroller=microcontroller,
                connection=connection,
                action="WRITE",
                params={"state": state},
            )

            if state == "off":
                self.stream_controller.stop_stream(microcontroller, connection)

            return response

        return tool_function

    def _build_state_toggle_tool_function(
        self,
        microcontroller: Microcontroller,
        connection,
        state: str,
    ):
        def tool_function() -> dict[str, str]:
            return self._send_connection_command(
                microcontroller=microcontroller,
                connection=connection,
                action="WRITE",
                params={"state": state},
            )

        return tool_function

    def _send_connection_command(
        self,
        microcontroller: Microcontroller,
        connection,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        serial_connection = self._get_serial_connection(microcontroller)
        built_command = CommandCompiler.build_command(
            connection,
            action=action,
            params=params,
        )

        event_name = connection.event_name
        event = self.event_bus.get_handler(("MCP", microcontroller.id, event_name))
        event.clear_responses()

        write = getattr(serial_connection, "write", None)
        if callable(write):
            write(built_command)
        else:
            response = serial_connection.send(built_command)
            if response:
                return CommandCompiler.parse_response(response)

        return event.wait_for_response()

    def close(self) -> None:
        if self.event_listener is not None:
            self.event_listener.stop_listeners()
            self.event_listener = None

        self.stream_controller.flush_all()
        event_worker.stop()

        for serial_connection in self.serial_pool.values():
            serial_connection.destroy()

        self.serial_pool.clear()

    def run(
        self,
        transport: str = "stdio",
        **transport_kwargs,
    ) -> None:
        self._register_serial_connection()
        self._start_event_listener()
        self.app.run(
            transport=transport,
            **transport_kwargs,
        )
