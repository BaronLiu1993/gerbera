from collections import deque

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.movement_system import (
    ContinuousJoint,
    FixedJoint,
    Joint,
    MovementSystem,
    PrismaticJoint,
    RevoluteJoint,
)

JOINT_MOTOR_COMPONENT_TYPES = {
    "revolute": {"sg90", "mg996r"},
    "prismatic": set(),
    "continuous": {"dcmotor"},
}


class MovementSystemValidator:
    @classmethod
    def validate(
        cls,
        movement_system: MovementSystem,
        registered_connections: dict[str, Connection],
    ) -> list[str]:
        errors: list[str] = []
        movement_path = (
            f"movement_systems[{movement_system.name.strip() or '<empty>'}]"
        )
        base_link_name = movement_system.base_link.name.strip()
        base_link_key = base_link_name.casefold()
        if not base_link_name:
            errors.append(f"{movement_path}.base_link.name: cannot be empty")

        joint_names: set[str] = set()
        link_names: set[str] = {base_link_key} if base_link_key else set()
        child_links: set[str] = set()
        adjacency: dict[str, list[str]] = (
            {base_link_key: []} if base_link_key else {}
        )
        incoming_edge_counts: dict[str, int] = (
            {base_link_key: 0} if base_link_key else {}
        )

        for joint in movement_system.joints:
            errors.extend(
                cls._validate_joint(
                    joint=joint,
                    movement_path=movement_path,
                    base_link_key=base_link_key,
                    joint_names=joint_names,
                    link_names=link_names,
                    child_links=child_links,
                    adjacency=adjacency,
                    incoming_edge_counts=incoming_edge_counts,
                    registered_connections=registered_connections,
                )
            )

        errors.extend(
            cls._validate_acyclic(
                movement_path=movement_path,
                link_names=link_names,
                adjacency=adjacency,
                incoming_edge_counts=incoming_edge_counts,
            )
        )
        if base_link_key:
            errors.extend(
                cls._validate_reachability(
                    movement_path=movement_path,
                    base_link_key=base_link_key,
                    link_names=link_names,
                    adjacency=adjacency,
                )
            )
        return errors

    @classmethod
    def _validate_joint(
        cls,
        *,
        joint: Joint,
        movement_path: str,
        base_link_key: str,
        joint_names: set[str],
        link_names: set[str],
        child_links: set[str],
        adjacency: dict[str, list[str]],
        incoming_edge_counts: dict[str, int],
        registered_connections: dict[str, Connection],
    ) -> list[str]:
        errors: list[str] = []
        joint_name = joint.name.strip()
        joint_key = joint_name.casefold()
        joint_path = f"{movement_path}.joints[{joint_name or '<empty>'}]"

        if not joint_name:
            errors.append(f"{joint_path}.name: cannot be empty")
        elif joint_key in joint_names:
            errors.append(f"{joint_path}.name: duplicate joint name")
        elif joint_key in link_names:
            errors.append(f"{joint_path}.name: conflicts with link name")
        else:
            joint_names.add(joint_key)

        parent_link_name = joint.parent_link.name.strip()
        child_link_name = joint.child_link.name.strip()
        parent_link_key = parent_link_name.casefold()
        child_link_key = child_link_name.casefold()

        if not parent_link_name:
            errors.append(f"{joint_path}.parent_link.name: cannot be empty")
        if not child_link_name:
            errors.append(f"{joint_path}.child_link.name: cannot be empty")

        for field_name, link_name, link_key in (
            ("parent_link", parent_link_name, parent_link_key),
            ("child_link", child_link_name, child_link_key),
        ):
            if link_key and link_key in joint_names:
                errors.append(
                    f"{joint_path}.{field_name}.name: link name conflicts with "
                    f"joint name: {link_name}"
                )
            if link_key:
                link_names.add(link_key)

        errors.extend(
            cls._validate_joint_configuration(
                joint=joint,
                joint_path=joint_path,
            )
        )
        errors.extend(
            cls._validate_motor(
                joint=joint,
                joint_path=joint_path,
                registered_connections=registered_connections,
            )
        )

        if not parent_link_key or not child_link_key:
            return errors

        adjacency.setdefault(parent_link_key, [])
        adjacency.setdefault(child_link_key, [])
        incoming_edge_counts.setdefault(parent_link_key, 0)
        incoming_edge_counts.setdefault(child_link_key, 0)

        if parent_link_key == child_link_key:
            errors.append(f"{joint_path}: cannot connect a link to itself")
            return errors

        if child_link_key == base_link_key:
            errors.append(f"{joint_path}.child_link: base link cannot be a child")

        if child_link_key in child_links:
            errors.append(
                f"{joint_path}.child_link: link has multiple parent joints: "
                f"{child_link_name}"
            )
        else:
            child_links.add(child_link_key)

        adjacency[parent_link_key].append(child_link_key)
        incoming_edge_counts[child_link_key] += 1
        return errors

    @staticmethod
    def _validate_joint_configuration(
        *,
        joint: Joint,
        joint_path: str,
    ) -> list[str]:
        errors: list[str] = []
        if len(joint.parent_to_joint_xyz_m) != 3:
            errors.append(
                f"{joint_path}.parent_to_joint_xyz_m: must contain 3 values"
            )
        if len(joint.parent_to_joint_rpy_rad) != 3:
            errors.append(
                f"{joint_path}.parent_to_joint_rpy_rad: must contain 3 values"
            )

        if isinstance(joint, (RevoluteJoint, PrismaticJoint, ContinuousJoint)):
            if joint.axis not in ("x", "y", "z"):
                errors.append(
                    f"{joint_path}.axis: must be one of x, y, or z: "
                    f"{joint.axis}"
                )

        if isinstance(joint, RevoluteJoint) and joint.lower_rad > joint.upper_rad:
            errors.append(
                f"{joint_path}.limits: lower_rad cannot exceed upper_rad"
            )
        if isinstance(joint, PrismaticJoint) and joint.lower_m > joint.upper_m:
            errors.append(
                f"{joint_path}.limits: lower_m cannot exceed upper_m"
            )
        return errors

    @staticmethod
    def _validate_motor(
        *,
        joint: Joint,
        joint_path: str,
        registered_connections: dict[str, Connection],
    ) -> list[str]:
        if isinstance(joint, FixedJoint):
            return []

        if joint.joint_type not in JOINT_MOTOR_COMPONENT_TYPES:
            return [f"{joint_path}.joint_type: unsupported type: {joint.joint_type}"]

        motor_connection = joint.motor_connection
        connection_name = motor_connection.name.strip()
        normalized_connection_name = connection_name.casefold()
        errors: list[str] = []

        registered_connection = registered_connections.get(
            normalized_connection_name
        )
        if registered_connection is None:
            errors.append(
                f"{joint_path}.motor_connection: connection is not registered: "
                f"{connection_name}"
            )
        elif registered_connection is not motor_connection:
            errors.append(
                f"{joint_path}.motor_connection: must reference the registered "
                f"connection object: {connection_name}"
            )

        component_type = motor_connection.component_type.strip().casefold()
        valid_component_types = JOINT_MOTOR_COMPONENT_TYPES[joint.joint_type]
        if component_type not in valid_component_types:
            errors.append(
                f"{joint_path}.motor_connection.component_type: "
                f"{motor_connection.component_type} is incompatible with "
                f"{joint.joint_type}"
            )

        return errors

    @staticmethod
    def _validate_acyclic(
        *,
        movement_path: str,
        link_names: set[str],
        adjacency: dict[str, list[str]],
        incoming_edge_counts: dict[str, int],
    ) -> list[str]:
        remaining_counts = incoming_edge_counts.copy()
        queue = deque(
            link_name
            for link_name, incoming_count in remaining_counts.items()
            if incoming_count == 0
        )
        visited: set[str] = set()

        while queue:
            link_name = queue.popleft()
            if link_name in visited:
                continue
            visited.add(link_name)
            for child_link in adjacency[link_name]:
                remaining_counts[child_link] -= 1
                if remaining_counts[child_link] == 0:
                    queue.append(child_link)

        if len(visited) != len(link_names):
            return [f"{movement_path}: contains a cycle"]
        return []

    @staticmethod
    def _validate_reachability(
        *,
        movement_path: str,
        base_link_key: str,
        link_names: set[str],
        adjacency: dict[str, list[str]],
    ) -> list[str]:
        visited: set[str] = set()
        queue = deque([base_link_key])

        while queue:
            link_name = queue.popleft()
            if link_name in visited:
                continue
            visited.add(link_name)
            queue.extend(adjacency[link_name])

        unreachable_links = sorted(link_names - visited)
        if unreachable_links:
            return [
                f"{movement_path}: links are not reachable from base link: "
                f"{', '.join(unreachable_links)}"
            ]
        return []
