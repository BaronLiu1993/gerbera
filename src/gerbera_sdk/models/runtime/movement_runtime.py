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
    joint_motor_mapping: dict[str, dict[str, object]] = field(
        default_factory=dict
    )

    def register_movement_limitations(self) -> None:
        joints = self.hardware_system.movement_system.joints

        for joint in joints:
            if isinstance(joint, FixedJoint):
                continue

            motor_connection_name = joint.motor_connection.name
            if motor_connection_name in self.joint_motor_mapping:
                raise KeyError(
                    "Movement joint motor mapping already exists: "
                    f"{motor_connection_name}"
                )

            if isinstance(joint, RevoluteJoint):
                self.joint_motor_mapping[motor_connection_name] = {
                    "joint_type": joint.joint_type,
                    "joint_name": joint.joint_name,
                    "axis": joint.axis,
                    "lower_rad": joint.lower_rad,
                    "upper_rad": joint.upper_rad,
                    "motor_connection": motor_connection_name,
                }
            elif isinstance(joint, PrismaticJoint):
                self.joint_motor_mapping[motor_connection_name] = {
                    "joint_type": joint.joint_type,
                    "joint_name": joint.joint_name,
                    "axis": joint.axis,
                    "lower_m": joint.lower_m,
                    "upper_m": joint.upper_m,
                    "motor_connection": motor_connection_name,
                }
            elif isinstance(joint, ContinuousJoint):
                self.joint_motor_mapping[motor_connection_name] = {
                    "joint_type": joint.joint_type,
                    "joint_name": joint.joint_name,
                    "axis": joint.axis,
                    "motor_connection": motor_connection_name,
                }
            else:
                raise TypeError(f"Unsupported movable joint: {type(joint)}")

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
            "configuration": (
                None
                if isinstance(joint, FixedJoint)
                else self.joint_motor_mapping[joint.motor_connection.name]
            ),
        }
