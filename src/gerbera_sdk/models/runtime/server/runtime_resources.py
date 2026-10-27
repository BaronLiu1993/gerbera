from dataclasses import dataclass

from mcp.types import ToolAnnotations

from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry, ToolDefinition
import json

from fastmcp import FastMCP
from gerbera_protocol import RuntimeManifest
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime
from gerbera_sdk.events.event_listener import EventListener


@dataclass
class RuntimeResources:
    tools: McpToolRegistry
    app: FastMCP
    hardware_system: HardwareSystem
    hardware_plan: HardwarePlan
    event_listener: EventListener
    hardware_runtime: HardwareRuntime
    model_runtime: ModelRuntime

    def register_remote_resources(self) -> None:
        @self.app.resource("gerbera://manifest", mime_type="application/json")
        def runtime_manifest() -> str:
            return RuntimeManifest(
                instance_id=self.hardware_system.id,
            ).model_dump_json()

        @self.app.resource("gerbera://hardware/state", mime_type="application/json")
        def hardware_state() -> str:
            return json.dumps(self.hardware_runtime.get_state_store())

        @self.app.resource("gerbera://environment/state", mime_type="application/json")
        def environment_state() -> str:
            return json.dumps(self.model_runtime.get_model_state())

        @self.app.resource("gerbera://health", mime_type="application/json")
        def listener_health() -> str:
            return json.dumps(self.event_listener.get_health())

        @self.app.resource("gerbera://hardware", mime_type="application/json")
        def hardware_description() -> str:
            return json.dumps({
                "name": self.hardware_system.name,
                "description": self.hardware_system.description,
                "boards": [
                    {
                        "id": board.microcontroller_id,
                        "name": board.name,
                        "fqbn": board.definition.fqbn,
                        "devices": [
                            {"name": connection.name, "type": connection.component_type}
                            for connection in board.connections
                        ],
                    }
                    for board in self.hardware_plan.boards
                ],
                "cameras": [camera.name for camera in self.hardware_system.cameras],
            })

    def register_event_listener_health_tool(self) -> None:
        self.tools.register(ToolDefinition(
            name="get_event_listener_health",
            description="Get serial listener health for each board.",
            tool_function=self.event_listener.get_health,
            annotations=ToolAnnotations(
                title="Get event listener health",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))

    def register_hardware_state_tool(self) -> None:
        self.tools.register(ToolDefinition(
            name="get_current_hardware_state",
            description=("Read the current hardware state memory."),
            tool_function=self.hardware_runtime.get_state_store,
            annotations=ToolAnnotations(
                title="Get current hardware state",
                readOnlyHint=True,
            ),
        ))

    def register_environment_state_tool(self) -> None:
        self.tools.register(ToolDefinition(
            name="get_current_environment_state",
            description=("Read the current environment state from model outputs."),
            tool_function=self.model_runtime.get_model_state,
            annotations=ToolAnnotations(
                title="Get current environment state",
                readOnlyHint=True,
            ),
        ))
