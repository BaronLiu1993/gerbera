import json

from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeWatchdogConfig,
)


def test_runtime_binds_connections_to_their_microcontroller(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "devices": {
                    "/dev/test": {
                        "id": "board-a",
                        "address": "/dev/test",
                    }
                }
            }
        )
    )
    connection = Connection(
        name="sensor",
        description="Test sensor",
        component_type="hcsr04",
        pins={"trig": "4", "echo": "5"},
    )
    hardware_system = HardwareSystem(
        id="system-1",
        name="Test system",
        description="Test hardware system",
        microcontrollers=[
            Microcontroller(
                name="Test board",
                fqbn="arduino:avr:uno",
                port="/dev/test",
                watchdog=RuntimeWatchdogConfig(
                    heartbeat_interval_ms=100,
                    heartbeat_timeout_ms=500,
                ),
                connections=[connection],
                config_path=config_path,
            )
        ],
    )

    GerberaRuntime.bind_connection_microcontroller_ids(hardware_system)

    assert connection.microcontroller_id == "board-a"
    assert hardware_system.microcontrollers[0].hardware_system_id == "system-1"

def test_runtime_builds_writer_database_from_explicit_connection_details() -> None:
    database = GerberaRuntime.runtime_database(
        host="database.internal",
        port=5432,
        password="secret",
    )

    assert database == Database(
        host="database.internal",
        port=5432,
        user="gerbera_writer",
        password="secret",
        database_name="gerbera",
    )
