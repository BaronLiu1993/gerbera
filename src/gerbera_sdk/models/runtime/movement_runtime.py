from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
import xml.etree.ElementTree as ET

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
    joint_motor_mapping: dict[str, dict[str, object]] = field(default_factory=dict)
    urdf_file_path: Path = Path(".gerbera/schematics/movement.urdf")
    urdf_axis_by_name: ClassVar[dict[str, str]] = {
        "x": "1 0 0",
        "y": "0 1 0",
        "z": "0 0 1",
    }

    def to_urdf(
        self,
    ) -> None:
        path = self.urdf_file_path
        movement_system = self.hardware_system.movement_system
        robot = ET.Element(
            "robot",
            {
                "name": self.hardware_system.name,
            },
        )
        link_names = {movement_system.base_link.name}

        for joint in movement_system.joints:
            link_names.add(joint.parent_link.name)
            link_names.add(joint.child_link.name)

        for link_name in sorted(link_names):
            ET.SubElement(robot, "link", {"name": link_name})

        for joint in movement_system.joints:
            joint_element = ET.SubElement(
                robot,
                "joint",
                {
                    "name": joint.joint_name,
                    "type": joint.joint_type,
                },
            )
            ET.SubElement(
                joint_element,
                "parent",
                {"link": joint.parent_link.name},
            )
            ET.SubElement(
                joint_element,
                "child",
                {"link": joint.child_link.name},
            )
            ET.SubElement(
                joint_element,
                "origin",
                {
                    "xyz": " ".join(
                        str(value) for value in joint.parent_to_joint_xyz_m
                    ),
                    "rpy": " ".join(
                        str(value) for value in joint.parent_to_joint_rpy_rad
                    ),
                },
            )

            if isinstance(
                joint,
                (RevoluteJoint, PrismaticJoint, ContinuousJoint),
            ):
                ET.SubElement(
                    joint_element,
                    "axis",
                    {"xyz": self.urdf_axis_by_name[joint.axis]},
                )

            if isinstance(joint, RevoluteJoint):
                ET.SubElement(
                    joint_element,
                    "limit",
                    {
                        "lower": str(joint.lower_rad),
                        "upper": str(joint.upper_rad),
                        "effort": "0",
                        "velocity": "0",
                    },
                )
            elif isinstance(joint, PrismaticJoint):
                ET.SubElement(
                    joint_element,
                    "limit",
                    {
                        "lower": str(joint.lower_m),
                        "upper": str(joint.upper_m),
                        "effort": "0",
                        "velocity": "0",
                    },
                )

        ET.indent(robot)
        urdf = ET.tostring(robot, encoding="unicode")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(urdf)

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

    def solve_forward_kinematics():
        pass

    def solve_inverse_kinematics():
        pass
