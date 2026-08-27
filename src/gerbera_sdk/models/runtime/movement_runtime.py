from dataclasses import asdict, dataclass
from typing import Any

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class MovementRuntime:
    hardware_system: HardwareSystem

    def get_movement_system(self) -> dict[str, Any]:
        movement_system = self.hardware_system.movement_system
        link_names = {movement_system.base_link.name}
        adjacency: dict[str, list[dict[str, Any]]] = {
            movement_system.base_link.name: []
        }
        joints: list[dict[str, Any]] = []

        for joint in movement_system.joints:
            link_names.add(joint.parent_link.name)
            link_names.add(joint.child_link.name)
            adjacency.setdefault(joint.parent_link.name, [])
            adjacency.setdefault(joint.child_link.name, [])
            adjacency[joint.parent_link.name].append(
                {
                    "joint_name": joint.joint_name,
                    "child_link": joint.child_link.name,
                }
            )
            joints.append(asdict(joint))

        return {
            "base_link": movement_system.base_link.name,
            "links": sorted(link_names),
            "joints": joints,
            "adjacency": adjacency,
        }
