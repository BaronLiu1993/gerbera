from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.hardware.movement_system import MovementSystem


def validate_hardware_system(hardware_system: HardwareSystem) -> str | None:
    microcontroller_ids: set[str] = set()
    camera_ids: set[str] = set()
    connection_owners: dict[str, str] = {}

    for microcontroller in hardware_system.microcontrollers:
        microcontroller_id = microcontroller.id
        if microcontroller_id in microcontroller_ids:
            return f"Duplicate microcontroller id: {microcontroller_id}"
        microcontroller_ids.add(microcontroller_id)
        error = validate_microcontroller(microcontroller)
        if error is not None:
            return error

        for connection in microcontroller.connections:
            normalized_name = connection.name.strip().lower()
            existing_owner = connection_owners.get(normalized_name)
            if existing_owner is not None:
                return (
                    f"Connection name must be globally unique: "
                    f"{connection.name}. Used by microcontrollers "
                    f"{existing_owner} and {microcontroller_id}"
                )
            connection_owners[normalized_name] = microcontroller_id

    for camera in hardware_system.cameras:
        if camera.camera_id in camera_ids:
            return f"Duplicate camera id: {camera.camera_id}"
        camera_ids.add(camera.camera_id)

    if hardware_system.movement_system is not None:
        return validate_movement_system(hardware_system.movement_system)

    return None


def validate_microcontroller(microcontroller: Microcontroller) -> str | None:
    connection_names: set[str] = set()
    used_pins: set[str] = set()

    for connection in microcontroller.connections:
        error = validate_connection_and_pins(
            connection=connection,
            connection_names=connection_names,
            used_pins=used_pins,
            microcontroller_id=microcontroller.id,
        )
        if error is not None:
            return error

    return None


def validate_connection_and_pins(
    *,
    connection: Connection,
    connection_names: set[str],
    used_pins: set[str],
    microcontroller_id: str,
) -> str | None:
    normalized_name = connection.name.strip().lower()
    if not normalized_name:
        return "Connection name cannot be empty"

    if normalized_name in connection_names:
        return f"Duplicate connection name on board {microcontroller_id}: {connection.name}"
    connection_names.add(normalized_name)

    for pin in connection.pins.values():
        if pin in used_pins:
            return f"Pin already in use on board {microcontroller_id}: {pin}"
        used_pins.add(pin)

    return None


def validate_movement_system(movement_system: MovementSystem) -> str | None:
    base_link_name = movement_system.base_link.name.strip()
    if not base_link_name:
        return "Movement base link name cannot be empty"

    link_names = {base_link_name}
    joint_names: set[str] = set()
    child_links: set[str] = set()
    adjacency: dict[str, list[str]] = {base_link_name: []}
    incoming_edge_counts: dict[str, int] = {base_link_name: 0}

    for joint in movement_system.joints:
        joint_name = joint.joint_name.strip()
        if not joint_name:
            return "Movement joint name cannot be empty"

        normalized_joint_name = joint_name.lower()
        if normalized_joint_name in joint_names:
            return f"Duplicate movement joint name: {joint.joint_name}"
        joint_names.add(normalized_joint_name)

        parent_link = joint.parent_link.name.strip()
        child_link = joint.child_link.name.strip()
        if not parent_link:
            return f"Movement joint {joint_name} parent link name cannot be empty"
        if not child_link:
            return f"Movement joint {joint_name} child link name cannot be empty"

        link_names.add(parent_link)
        link_names.add(child_link)
        adjacency.setdefault(parent_link, [])
        adjacency.setdefault(child_link, [])
        incoming_edge_counts.setdefault(parent_link, 0)
        incoming_edge_counts.setdefault(child_link, 0)

        if parent_link == child_link:
            return f"Movement joint cannot connect a link to itself: {joint_name}"

        if child_link == base_link_name:
            return "Movement base link cannot be a child link"

        if child_link in child_links:
            return f"Movement link has multiple parent joints: {child_link}"
        child_links.add(child_link)

        adjacency[parent_link].append(child_link)
        incoming_edge_counts[child_link] += 1

    topological_queue = [
        link_name
        for link_name, incoming_count in incoming_edge_counts.items()
        if incoming_count == 0
    ]
    visited_in_topological_order: set[str] = set()

    while topological_queue:
        link_name = topological_queue.pop(0)
        if link_name in visited_in_topological_order:
            continue

        visited_in_topological_order.add(link_name)
        for child_link in adjacency.get(link_name, []):
            incoming_edge_counts[child_link] -= 1
            if incoming_edge_counts[child_link] == 0:
                topological_queue.append(child_link)

    if len(visited_in_topological_order) != len(link_names):
        return "Movement system contains a cycle"

    visited: set[str] = set()
    queue = [base_link_name]

    while queue:
        link_name = queue.pop(0)
        if link_name in visited:
            continue

        visited.add(link_name)
        queue.extend(adjacency.get(link_name, []))

    unreachable_links = sorted(link_names - visited)
    if unreachable_links:
        return f"Movement links are not reachable from base link: {unreachable_links[0]}"

    return None
