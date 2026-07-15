import pytest

from gerbera_sdk import Connection, Database, HardwareSystem, Microcontroller


def _write_registry(tmp_path, board_id: str = "board-1", port: str = "/dev/cu.usbserial-1140"):
    registry_path = tmp_path / "config.json"
    registry_path.write_text(
        f"""
{{
  "devices": {{
    "{board_id}": {{
      "id": "{board_id}",
      "device": "{port}"
    }}
  }},
  "entry_point": "serve_mcp.py"
}}
""".strip()
    )
    return registry_path


def test_microcontroller_requires_registry_match_from_port() -> None:
    with pytest.raises(
        ValueError,
        match="Microcontroller id must be resolved from config.json\\['devices'\\] via port",
    ):
        Microcontroller()


def test_microcontroller_resolves_stable_id_from_port_registry(
    tmp_path,
    monkeypatch,
) -> None:
    registry_path = tmp_path / "config.json"
    registry_path.write_text(
        """
{
  "devices": {
    "27b30005-ff68-4c81-93ec-8d3ce7c7a242": {
      "id": "27b30005-ff68-4c81-93ec-8d3ce7c7a242",
      "device": "/dev/cu.usbserial-1140"
    }
  },
  "entry_point": "serve_mcp.py"
}
""".strip()
    )
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )

    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")

    assert microcontroller.id == "27b30005-ff68-4c81-93ec-8d3ce7c7a242"


def test_microcontroller_resolves_id_from_registry_port(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")

    assert microcontroller.id == "board-1"


def test_hardware_system_id_defaults_to_uuid() -> None:
    hardware_system = HardwareSystem()

    assert hardware_system.id


def test_hardware_system_sets_microcontroller_parent_id(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")

    hardware_system.add_microcontrollers([microcontroller])

    assert microcontroller.hardware_system_id == "system-1"
    assert hardware_system.microcontrollers == [microcontroller]


def test_microcontroller_sets_connection_parent_id(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")
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


def test_microcontroller_requires_hardware_system_before_connections(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")
    connection = Connection(
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )

    with pytest.raises(ValueError, match="must belong to a hardware system"):
        microcontroller.add_connections([connection])


def test_microcontroller_normalizes_connection_parent_to_resolved_id(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(port="/dev/cu.usbserial-1140")
    connection = Connection(
        microcontroller_id="board-2",
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])
    assert connection.microcontroller_id == "board-1"


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


def test_hardware_system_passes_database_to_microcontroller(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="gerbera",
    )
    hardware_system = HardwareSystem(id="system-1", database=database)
    microcontroller = Microcontroller(
        hardware_system_id="system-1",
        port="/dev/cu.usbserial-1140",
        connections=[
            Connection(
                name="obstacle_sensor",
                component_type="hw201",
                pins={"out": "7"},
            )
        ],
    )

    hardware_system.add_microcontrollers([microcontroller])

    assert microcontroller.database is database


def test_microcontroller_passes_database_to_connection(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
    database = Database(
        host="localhost",
        port=5432,
        user="user",
        password="password",
        databaseName="gerbera",
    )
    hardware_system = HardwareSystem(id="system-1")
    microcontroller = Microcontroller(
        port="/dev/cu.usbserial-1140",
        database=database,
    )
    connection = Connection(
        name="obstacle_sensor",
        component_type="hw201",
        pins={"out": "7"},
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])

    assert connection.database is database


def test_explicit_connection_database_is_not_overwritten(tmp_path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path)
    monkeypatch.setattr(
        "gerbera_sdk.models.microcontroller.CONFIG_PATH",
        registry_path,
    )
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
    microcontroller = Microcontroller(
        port="/dev/cu.usbserial-1140",
        database=inherited_database,
    )
    connection = Connection(
        name="obstacle_sensor",
        component_type="hw201",
        pins={"out": "7"},
        database=explicit_database,
    )

    hardware_system.add_microcontrollers([microcontroller])
    microcontroller.add_connections([connection])

    assert connection.database is explicit_database
