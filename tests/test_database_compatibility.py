import pytest

from gerbera_sdk import Connection, HardwareSystem, Microcontroller
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.firmware.devices.hcsr04 import HCSR04FirmwareBuilder
from gerbera_sdk.firmware.devices.hw201 import HW201FirmwareBuilder
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder


class FakeDatabase:
    def __init__(self) -> None:
        self.hardware_system_id = ""
        self.created_tables: list[tuple[str, object]] = []

    def create_database_table(self, table_name: str, schema) -> None:
        self.created_tables.append((table_name, schema))

    def to_dict(self) -> dict[str, str]:
        return {"hardware_system_id": self.hardware_system_id}


def test_database_compatibility_is_explicit_per_builder() -> None:
    assert LEDFirmwareBuilder.supports_database is False
    assert HW201FirmwareBuilder.supports_database is True
    assert HCSR04FirmwareBuilder.supports_database is True


def test_database_is_not_propagated_to_every_connection() -> None:
    database = FakeDatabase()
    connection = Connection(
        id="green-led",
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )
    microcontroller = Microcontroller(
        id="board-1",
        hardware_system_id="system-1",
        connections=[connection],
    )

    HardwareSystem(
        id="system-1",
        microcontrollers=[microcontroller],
        database=database,
    )

    assert database.hardware_system_id == "system-1"
    assert connection.database is None
    assert microcontroller.database is None


def test_database_on_unsupported_connection_raises() -> None:
    with pytest.raises(ValueError, match="led does not support database streaming"):
        Connection(
            id="green-led",
            name="green_led",
            component_type="led",
            pins={"out": "13"},
            database=FakeDatabase(),
            event_bus=EventBus(),
        )


def test_database_table_name_uses_microcontroller_id_and_connection_name() -> None:
    database = FakeDatabase()

    Connection(
        id="obstacle-sensor",
        name="obstacle_sensor",
        microcontroller_id="27b30005-ff68-4c81-93ec-8d3ce7c7a242",
        component_type="hw201",
        pins={"out": "7"},
        database=database,
        event_bus=EventBus(),
    )

    table_name = database.created_tables[0][0]
    assert table_name == "hw201_8e910dfb_e8f75c2b"
    assert len(table_name) <= 63


def test_event_name_is_capped_for_postgres_identifiers() -> None:
    connection = Connection(
        name="very_long_sensor_name_that_would_otherwise_create_a_postgres_identifier_that_is_far_too_long",
        microcontroller_id="27b30005-ff68-4c81-93ec-8d3ce7c7a242",
        component_type="hcsr04",
        pins={"trig": "8", "echo": "9"},
    )

    assert len(connection.event_name) <= 63
    assert connection.event_name.startswith("hcsr04_8e910dfb_")
    assert "very_long_sensor_name" not in connection.event_name
