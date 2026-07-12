from gerbera_sdk.contracts.command_contract import CommandSpec
from typing import Optional

from gerbera_sdk.server.commands import CommandCompiler
from gerbera_sdk.server.serial_connection import SerialConnection
from gerbera_sdk.models.hardware_system import HardwareSystem
from gerbera_sdk.models.microcontroller import Microcontroller
from fastmcp import FastMCP


class GerberaServer:
    def __init__(self, hardware_system: HardwareSystem) -> None:
        self.hardware_system = hardware_system
        self.serial_pool: dict[str, SerialConnection] = {}
        self.app = FastMCP(hardware_system.description)
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
                connection = SerialConnection()
                connection.connect(
                    port=microcontroller.port,
                    baud=microcontroller.baud_rate,
                )
                microcontroller_id = microcontroller.id
                self.serial_pool[microcontroller_id] = connection
        except Exception as e:
            raise RuntimeError(e)

    def _register_tools(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                for command in CommandCompiler.command_specs(connection):
                    self._register_connection_tool(
                        microcontroller,
                        connection,
                        command,
                    )

    def _register_connection_tool(
        self,
        microcontroller: Microcontroller,
        connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()
        tool_name = f"{action.lower()}_{connection.name}"

        def tool_function(
            params: Optional[dict[str, str]] = None,
            _microcontroller: Microcontroller = microcontroller,
            _connection=connection,
            _action: str = action,
        ) -> dict[str, str]:
            serial_connection = self._get_serial_connection(_microcontroller)
            built_command = CommandCompiler.build_command(
                _connection,
                action=_action,
                params=params,
            )
            response = serial_connection.send(built_command)

            return CommandCompiler.parse_response(response)

        tool_function.__name__ = tool_name

        command_description = CommandCompiler.describe_command(connection, action)
        tool_function.__doc__ = connection.description or (
            f"Send {command_description} over serial."
        )

        self.app.tool(
            name=tool_name,
            description=tool_function.__doc__,
        )(tool_function)

    def close(self) -> None:
        for serial_connection in self.serial_pool.values():
            serial_connection.destroy()

        self.serial_pool.clear()

    def run(
        self,
        transport: str = "stdio",
        **transport_kwargs,
    ) -> None:
        self.app.run(
            transport=transport,
            **transport_kwargs,
        )
