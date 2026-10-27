from dataclasses import dataclass

from gerbera_sdk.models.runtime.server.hardware_tools import HardwareTools
from gerbera_sdk.models.runtime.server.movement_tools import MovementTools
from gerbera_sdk.models.runtime.server.perception_tools import PerceptionTools
from gerbera_sdk.models.runtime.server.reaction_tools import ReactionTools
from gerbera_sdk.models.runtime.server.runtime_resources import RuntimeResources


@dataclass
class ServerRuntime:
    resources: RuntimeResources
    hardware: HardwareTools
    perception: PerceptionTools
    movement: MovementTools
    reactions: ReactionTools

    def register_tools(self) -> None:
        self.resources.register_remote_resources()
        self.hardware.register_hardware_tools()
        self.perception.register_camera_tools()
        self.perception.register_inference_tools()
        self.movement.register_movement_tools()
        self.reactions.register_reaction_tools()
        self.reactions.register_reaction_catalog_tool()
        self.resources.register_hardware_state_tool()
        self.resources.register_environment_state_tool()
        self.resources.register_event_listener_health_tool()
