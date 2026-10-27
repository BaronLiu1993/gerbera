from dataclasses import dataclass
from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry, ToolDefinition
from gerbera_sdk.models.runtime.movement.movement_runtime import MovementRuntime


@dataclass
class MovementTools:
    tools: McpToolRegistry
    movement_runtime: MovementRuntime | None

    def register_movement_tools(self) -> None:
        if self.movement_runtime is None:
            return

        def list_movement_systems() -> list[str]:
            return self.movement_runtime.list_movement_systems()

        def get_current_movement_state() -> dict[str, object]:
            return self.movement_runtime.get_movement_context()

        def solve_forward_kinematics(
            movement_system_name: str,
            target_link_name: str,
        ) -> dict[str, object]:
            return self.movement_runtime.solve_forward_kinematics(
                movement_system_name=movement_system_name,
                target_link_name=target_link_name,
            )

        def solve_inverse_kinematics(
            movement_system_name: str,
            target_link_name: str,
            target_position_m: Annotated[
                list[float],
                Field(min_length=3, max_length=3),
            ],
            target_orientation_rpy_rad: Annotated[
                list[float],
                Field(min_length=3, max_length=3),
            ],
        ) -> dict[str, float]:
            return self.movement_runtime.solve_inverse_kinematics(
                movement_system_name=movement_system_name,
                target_link_name=target_link_name,
                target_position_m=(
                    target_position_m[0],
                    target_position_m[1],
                    target_position_m[2],
                ),
                target_orientation_rpy_rad=(
                    target_orientation_rpy_rad[0],
                    target_orientation_rpy_rad[1],
                    target_orientation_rpy_rad[2],
                ),
            )

        self.tools.register(ToolDefinition(
            name="list_movement_systems",
            description="List registered movement system names.",
            tool_function=list_movement_systems,
            annotations=ToolAnnotations(
                title="List movement systems",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
        self.tools.register(ToolDefinition(
            name="get_current_movement_state",
            description=(
                "Read current movement system state, joint definitions, links, "
                "target links, motor connections, limits, and joint positions."
            ),
            tool_function=get_current_movement_state,
            annotations=ToolAnnotations(
                title="Get current movement state",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
        self.tools.register(ToolDefinition(
            name="solve_forward_kinematics",
            description=(
                "Compute the current pose of a target link in a registered "
                "movement system from the runtime joint positions."
            ),
            tool_function=solve_forward_kinematics,
            annotations=ToolAnnotations(
                title="Solve forward kinematics",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
        self.tools.register(ToolDefinition(
            name="solve_inverse_kinematics",
            description=(
                "Compute joint positions for a target link to reach a target "
                "position and roll-pitch-yaw orientation."
            ),
            tool_function=solve_inverse_kinematics,
            annotations=ToolAnnotations(
                title="Solve inverse kinematics",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
