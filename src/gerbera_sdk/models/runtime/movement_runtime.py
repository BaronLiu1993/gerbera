from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET
import ikpy.chain


from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.movement_system import (
    ContinuousJoint,
    FixedJoint,
    Joint,
    MovementSystem,
    PrismaticJoint,
    RevoluteJoint,
)


@dataclass
class MovementSystemRuntimeRegistry:
    movement_system: MovementSystem
    joint_by_name: dict[str, Joint]
    joint_path_by_target_link: dict[str, list[Joint]]
    joint_positions: dict[str, float | None]


@dataclass
class MovementRuntime:
    hardware_system: HardwareSystem
    movement_system_registry: dict[
        str,
        MovementSystemRuntimeRegistry,
    ] = field(default_factory=dict)
    urdf_file_path: str = ".gerbera/schematics"
    urdf_axis_by_name: dict[str, str] = field(
        default_factory=lambda: {
            "x": "1 0 0",
            "y": "0 1 0",
            "z": "0 0 1",
        }
    )

    def reset_motors_to_standard_position(self) -> None:
        results: dict[str, dict[str, float]] = {}

        for movement_system_name, movement_system in (
            self.movement_system_registry.items()
        ):
            joint_positions: dict[str, float] = {}

            for joint in movement_system.joint_by_name.values():
                if isinstance(joint, FixedJoint):
                    continue

                connection = joint.motor_connection
                response = connection.perform_action("WRITE", {"angle": 0.0})
                if not response.get("success"):
                    raise RuntimeError(
                        f"Failed to reset movement joint: {joint.name}"
                    )
                movement_system.joint_positions[joint.name] = 0.0
                joint_positions[joint.name] = 0.0

            results[movement_system_name] = joint_positions

    def solve_forward_kinematics(
        self,
        movement_system_name: str,
        target_link_name: str,
    ) -> dict[str, object]:
        registry = self.movement_system_registry[movement_system_name]
        target_link_path = registry.joint_path_by_target_link[target_link_name]
        joint_values = self.build_joint_values(
            registry=registry,
            joint_path=target_link_path,
        )

        movement_chain = ikpy.chain.Chain.from_urdf_file(
            f"{self.urdf_file_path}/{movement_system_name}.urdf"
        )
        transform = movement_chain.forward_kinematics(joint_values)

        return {
            "position_m": transform[:3, 3].tolist(),
            "transform": transform.tolist(),
        }

    def solve_inverse_kinematics(
        self,
        movement_system_name: str,
        target_link_name: str,
        target_position_m: tuple[float, float, float],
        target_orientation_rpy_rad: tuple[float, float, float],
    ) -> dict[str, float]:
        registry = self.movement_system_registry[movement_system_name]
        target_link_path = registry.joint_path_by_target_link[target_link_name]
        initial_position = self.build_joint_values(
            registry=registry,
            joint_path=target_link_path,
        )

        movement_chain = ikpy.chain.Chain.from_urdf_file(
            f"{self.urdf_file_path}/{movement_system_name}.urdf"
        )

        joint_values = movement_chain.inverse_kinematics(
            target_position=target_position_m,
            target_orientation=target_orientation_rpy_rad,
            initial_position=initial_position,
        )

        solution = {}
        for joint, joint_value in zip(target_link_path, joint_values[1:]):
            if isinstance(joint, FixedJoint):
                continue

            solution[joint.name] = float(joint_value)

        return solution

    def build_joint_values(
        self,
        registry: MovementSystemRuntimeRegistry,
        joint_path: list[Joint],
    ) -> list[float | None]:
        joint_values = [0.0]
        for joint in joint_path:
            if isinstance(joint, FixedJoint):
                joint_values.append(0.0)
            else:
                joint_values.append(registry.joint_positions.get(joint.name))
        return joint_values

    def register_movement_system(self) -> None:
        for movement_system in self.hardware_system.movement_systems:
            joint_positions = {}
            joint_by_name = {}
            for joint in movement_system.joints:
                joint_positions[joint.name] = None
                joint_by_name[joint.name] = joint
            joint_path_by_target_link = self.define_paths_from_base_link(
                movement_system.base_link, movement_system.joints
            )

            self.movement_system_registry[movement_system.name] = (
                MovementSystemRuntimeRegistry(
                    movement_system=movement_system,
                    joint_by_name=joint_by_name,
                    joint_positions=joint_positions,
                    joint_path_by_target_link=joint_path_by_target_link,
                )
            )
            self.write_urdf(movement_system)

    def define_paths_from_base_link(self, base_link, joints):
        adj_list: dict[str, list[Joint]] = {}
        for joint in joints:
            adj_list.setdefault(joint.parent_link.name, []).append(joint)

        paths_by_target_link: dict[str, list[Joint]] = {
            base_link.name: [],
        }
        queue = deque([base_link.name])
        visited = set()

        while queue:
            link_name = queue.popleft()
            if link_name in visited:
                continue

            visited.add(link_name)
            current_path = paths_by_target_link[link_name]

            for joint in adj_list.get(link_name, []):
                child_link_name = joint.child_link.name
                paths_by_target_link[child_link_name] = current_path + [joint]
                queue.append(child_link_name)

        return paths_by_target_link

    def write_urdf(self, movement_system: MovementSystem) -> None:
        robot = ET.Element("robot", {"name": movement_system.name})
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
                {"name": joint.name, "type": joint.joint_type},
            )
            ET.SubElement(joint_element, "parent", {"link": joint.parent_link.name})
            ET.SubElement(joint_element, "child", {"link": joint.child_link.name})
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

            if isinstance(joint, (RevoluteJoint, PrismaticJoint, ContinuousJoint)):
                ET.SubElement(
                    joint_element,
                    "axis",
                    {"xyz": self.urdf_axis_by_name[joint.axis]},
                )

            if isinstance(joint, RevoluteJoint):
                self.add_urdf_joint_limit(
                    joint_element,
                    lower=joint.lower_rad,
                    upper=joint.upper_rad,
                )
            elif isinstance(joint, PrismaticJoint):
                self.add_urdf_joint_limit(
                    joint_element,
                    lower=joint.lower_m,
                    upper=joint.upper_m,
                )

        ET.indent(robot)
        urdf_path = Path(self.urdf_file_path) / f"{movement_system.name}.urdf"
        urdf_path.parent.mkdir(parents=True, exist_ok=True)
        urdf_path.write_text(ET.tostring(robot, encoding="unicode"))

    def add_urdf_joint_limit(
        self,
        joint_element,
        lower: float,
        upper: float,
    ) -> None:
        ET.SubElement(
            joint_element,
            "limit",
            {
                "lower": str(lower),
                "upper": str(upper),
                "effort": "0",
                "velocity": "0",
            },
        )
