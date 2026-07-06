from typing import Any, Callable

from gerbera_sdk.hardware.connections import Connection
from gerbera_sdk.hardware.hardware_system import HardwareSystem
from gerbera_sdk.hardware.microcontroller import Microcontroller
from gerbera_sdk.mcp.transport_pool import SerialTransportPool

from fastmcp import FastMCP


class GerberaMCPServer:
    def __init__(
        self,
        hardware_system: HardwareSystem,
        server_name: str = "Gerbera MCP Server",
    ):
        self.hardware_system = hardware_system
        self.server_name = server_name
        self.transport_pool = SerialTransportPool(hardware_system)

    def create_server(self) -> Any:
        if FastMCP is None:
            raise ImportError(
                "fastmcp is not installed. Install it with `pip install fastmcp` "
                "or add the `mcp` optional dependency for this project."
            )

        return FastMCP(
            self.server_name,
            instructions=(
                "Expose Gerbera hardware connections as MCP tools. "
                "Use the overview tool first to inspect available boards and components."
            ),
            tools=self._build_tools(),
        )

    def run(self, **kwargs: Any) -> None:
        self.create_server().run(**kwargs)

    def close(self) -> None:
        self.transport_pool.close_all()

    def _build_tools(self) -> list[Callable[..., Any]]:
        tools: list[Callable[..., Any]] = [self._build_overview_tool()]

        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                tools.append(
                    self._build_connection_tool(
                        microcontroller=microcontroller,
                        connection=connection,
                    )
                )

        return tools

    def _build_overview_tool(self) -> Callable[[], dict[str, Any]]:
        def gerbera_hardware_overview() -> dict[str, Any]:
            return {
                "description": self.hardware_system.description,
                "microcontrollers": [
                    microcontroller.to_dict()
                    for microcontroller in self.hardware_system.microcontrollers
                ],
            }

        gerbera_hardware_overview.__doc__ = (
            "Return the modeled Gerbera hardware system, including boards, ports, "
            "component types, and MCP-facing schemas."
        )
        return gerbera_hardware_overview

    def _build_connection_tool(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> Callable[[], dict[str, Any]]:
        def tool() -> dict[str, Any]:
            return self.transport_pool.execute(
                microcontroller_id=microcontroller.id,
                connection_name=connection.name,
            )

        tool.__name__ = connection.name
        tool.__doc__ = (
            f"{connection.description} "
            f"(board={microcontroller.id}, component_type={connection.component_type})"
        )
        return tool
