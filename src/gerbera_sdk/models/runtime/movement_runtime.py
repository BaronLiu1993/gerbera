from collections import deque
from dataclasses import dataclass, field
from typing import Any
import ikpy


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
    joint_positions: dict[str, dict[float | None]]

@dataclass
class MovementRuntime:
    hardware_system: HardwareSystem
    movement_system_registry: dict[
        str,
        MovementSystemRuntimeRegistry,
    ] = field(default_factory=dict)

    # urdf_file_path: Path = Path(".gerbera/schematics/movement.urdf")
    # urdf_axis_by_name: ClassVar[dict[str, str]] = {
    #     "x": "1 0 0",
    #     "y": "0 1 0",
    #     "z": "0 0 1",
    # }

    def solve_forward_kinematics(
        self,
        movement_system_name: str, # the name of the movement system
        target_link_name: str, # end effector
    ) -> dict[str, Any]:
        movement_system = self.movement_system_registry[movement_system_name]
        target_link_path = movement_system.joint_path_by_target_link[target_link_name]
        joint_positions = movement_system.joint_positions
        chain = self.build_path_chain(target_link_path, joint_positions)
        chain.forward_kinematics()


    def build_path_chain(self):


        

    def solve_inverse_kinematics(self) -> None:
        pass

    def register_movements(self) -> None:
        for movement_system in self.hardware_system.movement_systems:
            movement_system_name = movement_system.name
            if movement_system_name in self.movement_system_registry:
                raise KeyError(
                    f"Movement system already registered: {movement_system_name}"
                )

            self.movement_system_registry[movement_system_name] = (
                MovementSystemRuntimeRegistry(
                    movement_system=movement_system,
                    joint_by_name=self.build_joint_by_name(movement_system),
                    joint_path_by_target_link=(
                        self.build_joint_path_by_target_link(movement_system)
                    ),
                )
            )

            for joint in movement_system.joints:
                if isinstance(joint, FixedJoint):
                    continue
                self.register_joint_motor_mapping(
                    movement_system_name=movement_system_name,
                    joint=joint,
                )

    def build_joint_by_name(
        self,
        movement_system: MovementSystem,
    ) -> dict[str, Joint]:
        joint_by_name: dict[str, Joint] = {}
        for joint in movement_system.joints:
            if joint.joint_name in joint_by_name:
                raise KeyError(f"Movement joint already registered: {joint.joint_name}")
            joint_by_name[joint.joint_name] = joint

        return joint_by_name

    def build_joint_path_by_target_link(
        self,
        movement_system: MovementSystem,
    ) -> dict[str, list[Joint]]:
        joints_by_parent_link: dict[str, list[Joint]] = {}
        for joint in movement_system.joints:
            joints_by_parent_link.setdefault(
                joint.parent_link.name,
                [],
            ).append(joint)

        joint_path_by_target_link: dict[str, list[Joint]] = {
            movement_system.base_link.name: [],
        }
        queue = deque([movement_system.base_link.name])

        while queue:
            parent_link_name = queue.popleft()
            parent_path = joint_path_by_target_link[parent_link_name]

            for joint in joints_by_parent_link.get(parent_link_name, []):
                child_link_name = joint.child_link.name
                joint_path_by_target_link[child_link_name] = parent_path + [joint]
                queue.append(child_link_name)

        return joint_path_by_target_link

    def register_joint_motor_mapping(
        self,
        movement_system_name: str,
        joint: MovableJoint,
    ) -> None:
        joint_key = (movement_system_name, joint.joint_name)
        motor_key = (movement_system_name, joint.motor_connection.name)

        if motor_key in self.motor_to_joint_mapping:
            raise KeyError(
                "Movement motor mapping already exists: "
                f"{movement_system_name},{joint.motor_connection.name}"
            )
        if joint_key in self.joint_to_motor_mapping:
            raise KeyError(
                "Movement joint mapping already exists: "
                f"{movement_system_name},{joint.joint_name}"
            )

        self.motor_to_joint_mapping[motor_key] = joint_key
        self.joint_to_motor_mapping[joint_key] = motor_key
        self.joint_positions[joint_key] = None

    def get_joint_configuration_for_motor(
        self,
        motor_connection_name: str,
    ) -> dict[str, object] | None:
        for motor_key, joint_key in self.motor_to_joint_mapping.items():
            if motor_key[1] != motor_connection_name:
                continue

            movement_system_name, joint_name = joint_key
            registry = self.movement_system_registry[movement_system_name]
            joint = registry.joint_by_name[joint_name]
            return self.build_joint_configuration(
                movement_system_name=movement_system_name,
                joint=joint,
                motor_connection_name=motor_connection_name,
            )

        return None

    def build_joint_configuration(
        self,
        movement_system_name: str,
        joint: Joint,
        motor_connection_name: str,
    ) -> dict[str, object]:
        configuration: dict[str, object] = {
            "movement_system_name": movement_system_name,
            "joint_type": joint.joint_type,
            "joint_name": joint.joint_name,
            "motor_connection": motor_connection_name,
        }

        if isinstance(joint, (RevoluteJoint, PrismaticJoint, ContinuousJoint)):
            configuration["axis"] = joint.axis
        if isinstance(joint, RevoluteJoint):
            configuration["lower_rad"] = joint.lower_rad
            configuration["upper_rad"] = joint.upper_rad
        elif isinstance(joint, PrismaticJoint):
            configuration["lower_m"] = joint.lower_m
            configuration["upper_m"] = joint.upper_m

        return configuration
