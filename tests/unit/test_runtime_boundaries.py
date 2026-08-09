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
        GerberaRuntime.validate_unique_connection_names(hardware_system)


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
        GerberaRuntime.validate_unique_connection_names(hardware_system)


def test_runtime_uses_local_writer_database_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GERBERA_DATABASE_HOST", raising=False)
    monkeypatch.delenv("GERBERA_DATABASE_PORT", raising=False)
    monkeypatch.delenv("GERBERA_WRITER_USER", raising=False)
    monkeypatch.delenv("GERBERA_WRITER_PASSWORD", raising=False)
    monkeypatch.delenv("GERBERA_DATABASE_NAME", raising=False)
    hardware_system = SimpleNamespace(
        microcontrollers=[
            SimpleNamespace(
                id="board-a",
                connections=[SimpleNamespace(database=None)],
            )
        ]
    )

    database = GerberaRuntime.runtime_database()

    assert database == Database(
        host="127.0.0.1",
        port=6432,
        user="gerbera_writer",
        password="writer_password",
        databaseName="gerbera",
    )

