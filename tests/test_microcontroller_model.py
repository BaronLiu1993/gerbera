from uuid import UUID

import pytest

from gerbera_sdk import Connection, Database, HardwareSystem, Microcontroller


def test_microcontroller_id_defaults_to_uuid() -> None:
    microcontroller = Microcontroller()

    UUID(microcontroller.id)
    assert microcontroller.microcontroller_id == microcontroller.id


def test_microcontroller_accepts_explicit_id() -> None:
    microcontroller = Microcontroller(id="board-1")

    assert microcontroller.id == "board-1"
    assert microcontroller.microcontroller_id == "board-1"


def test_hardware_system_id_defaults_to_uuid() -> None:
    hardware_system = HardwareSystem()

    UUID(hardware_system.id)


def test_hardware_system_sets_microcontroller_parent_id() -> None:
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(id="board-1")

    hardware_system.add_microcontrollers([microcontroller])

    assert microcontroller.hardware_system_id == "system-1"
    assert hardware_system.microcontrollers == [microcontroller]


def test_microcontroller_sets_connection_parent_id() -> None:
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(id="board-1")
    connection = Connection(
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])

    assert connection.hardware_system_id == "system-1"
    assert connection.microcontroller_id == "board-1"
    assert microcontroller.connections == [connection]


def test_microcontroller_requires_hardware_system_before_connections() -> None:
    microcontroller = Microcontroller(id="board-1")
    connection = Connection(
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )

    with pytest.raises(ValueError, match="must belong to a hardware system"):
        microcontroller.add_connections([connection])


def test_microcontroller_rejects_connection_for_different_parent() -> None:
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(id="board-1")
    connection = Connection(
        microcontroller_id="board-2",
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )

    hardware_system.add_microcontrollers([microcontroller])
    with pytest.raises(ValueError, match="belongs to microcontroller board-2"):
        microcontroller.add_connections([connection])


def test_hardware_system_sets_database_parent_id() -> None:
    database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="gerbera",
    )

    hardware_system = HardwareSystem(id="system-1", database=database)

    assert database.hardware_system_id == "system-1"
    assert hardware_system.database is database


def test_hardware_system_passes_database_to_microcontroller() -> None:
    database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="gerbera",
    )
    hardware_system = HardwareSystem(id="system-1", database=database)
    microcontroller = Microcontroller(id="board-1")

    hardware_system.add_microcontrollers([microcontroller])

    assert microcontroller.database is database


def test_microcontroller_passes_database_to_connection() -> None:
    database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="gerbera",
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(id="board-1", database=database)
    connection = Connection(
        name="obstacle_sensor",
        component_type="hw201",
        pins={"out": "7"},
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])

    assert connection.database is database


def test_explicit_connection_database_is_not_overwritten() -> None:
    inherited_database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="inherited",
    )
    explicit_database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="explicit",
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(id="board-1", database=inherited_database)
    connection = Connection(
        name="obstacle_sensor",
        component_type="hw201",
        pins={"out": "7"},
        database=explicit_database,
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])

    assert connection.database is explicit_database
