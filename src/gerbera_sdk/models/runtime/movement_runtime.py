from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.movement_system import (
    ContinuousJoint,
    FixedJoint,
    Joint,
    PrismaticJoint,
    RevoluteJoint,
)


@dataclass
class MovementRuntime:
    hardware_system: HardwareSystem
    movement_limitations: dict[str, dict[str, object] | None] = field(
        default_factory=dict
    )

    def get_joint_movement_limitation(self, joint_name: str):
        if joint_name not in self.movement_limitations:
            raise KeyError("Joint does not exist in the configuration")
        return self.movement_limitations[joint_name]

    def set_movement_limitations(self) -> None:
        joints = self.hardware_system.movement_system.joints
        self.movement_limitations = {}

        for joint in joints:
            if isinstance(joint, RevoluteJoint):
                self.movement_limitations[joint.joint_name] = {
                    "joint_type": joint.joint_type,
                    "axis": joint.axis,
                    "lower_rad": joint.lower_rad,
                    "upper_rad": joint.upper_rad,
                    "motor_connection": joint.motor_connection.name,
                }
            elif isinstance(joint, PrismaticJoint):
                self.movement_limitations[joint.joint_name] = {
                    "joint_type": joint.joint_type,
                    "axis": joint.axis,
                    "lower_m": joint.lower_m,
                    "upper_m": joint.upper_m,
                    "motor_connection": joint.motor_connection.name,
                }
            elif isinstance(joint, ContinuousJoint):
                self.movement_limitations[joint.joint_name] = {
                    "joint_type": joint.joint_type,
                    "axis": joint.axis,
                    "motor_connection": joint.motor_connection.name,
                }
            elif isinstance(joint, FixedJoint):
                self.movement_limitations[joint.joint_name] = None
            else:
                raise TypeError(f"Unsupported movement joint: {type(joint)}")

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
            joints.append(self.build_joint_payload(joint))

        return {
            "base_link": movement_system.base_link.name,
            "links": sorted(link_names),
            "joints": joints,
            "adjacency": adjacency,
        }

    def build_joint_payload(self, joint: Joint) -> dict[str, Any]:
        return {
            "joint_name": joint.joint_name,
            "joint_type": joint.joint_type,
            "parent_link": joint.parent_link.name,
            "child_link": joint.child_link.name,
            "parent_to_joint_xyz_m": joint.parent_to_joint_xyz_m,
            "parent_to_joint_rpy_rad": joint.parent_to_joint_rpy_rad,
            "description": joint.description,
            "configuration": self.get_joint_movement_limitation(
                joint.joint_name
            ),
        }
