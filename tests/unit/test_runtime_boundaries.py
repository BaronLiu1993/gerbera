from types import SimpleNamespace

import pytest

from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.database import Database


def test_runtime_rejects_globally_duplicate_connection_names() -> None:
    hardware_system = SimpleNamespace(
        microcontrollers=[
            SimpleNamespace(
                id="board-a",
                connections=[SimpleNamespace(name="Sensor")],
            ),
            SimpleNamespace(
                id="board-b",
                connections=[SimpleNamespace(name=" sensor ")],
            ),
        ]
    )

    with pytest.raises(ValueError, match="globally unique"):
        GerberaRuntime._validate_unique_connection_names(hardware_system)


def test_runtime_rejects_empty_connection_names() -> None:
    hardware_system = SimpleNamespace(
        microcontrollers=[
            SimpleNamespace(
                id="board-a",
                connections=[SimpleNamespace(name=" ")],
            )
        ]
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        GerberaRuntime._validate_unique_connection_names(hardware_system)


def test_runtime_requires_database() -> None:
    hardware_system = SimpleNamespace(
        microcontrollers=[
            SimpleNamespace(
                id="board-a",
                connections=[SimpleNamespace(database=None)],
            )
        ]
    )

    with pytest.raises(ValueError, match="requires a database"):
        GerberaRuntime._runtime_database(hardware_system)


def test_runtime_uses_configured_database() -> None:
    database = Database("localhost", 5432, "user", "password", "gerbera")
    hardware_system = SimpleNamespace(
        microcontrollers=[
            SimpleNamespace(
                id="board-a",
                connections=[SimpleNamespace(database=database)],
            )
        ]
    )

    assert GerberaRuntime._runtime_database(hardware_system) is database
