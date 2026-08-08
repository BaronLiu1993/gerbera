from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime


def _database() -> Database:
    return Database("localhost", 5432, "user", "password", "gerbera")


def test_database_runtime_does_not_start_worker_without_tables() -> None:
    class Worker(EventWorker):
        started = False

        def start(self) -> None:
            self.started = True

    worker = Worker()
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        event_worker=worker,
    )

    runtime.start()

    assert worker.started is False


def test_database_runtime_rejects_unsupported_streaming_component(
    monkeypatch,
) -> None:
    connection = Connection(
        "led",
        "led",
        {"out": "13"},
        microcontroller_id="board-1",
        stream=True,
    )
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(
            microcontrollers=[SimpleNamespace(connections=[connection])]
        ),
        event_worker=EventWorker(),
        database=_database(),
    )
    monkeypatch.setattr(
        runtime,
        "_create_database_table",
        lambda database, table_name, schema: None,
    )

    with pytest.raises(ValueError, match="does not support streaming"):
        runtime.start()


def test_database_runtime_creates_tables_for_streamed_connections(
    monkeypatch,
) -> None:
    connection = Connection(
        "distance",
        "hcsr04",
        {"trig": "4", "echo": "5"},
        microcontroller_id="board-1",
        stream=True,
    )
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(
            microcontrollers=[SimpleNamespace(connections=[connection])]
        ),
        event_worker=EventWorker(),
        database=_database(),
    )
    created_tables: list[str] = []

    monkeypatch.setattr(
        runtime,
        "_create_database_table",
        lambda database, table_name, schema: created_tables.append(table_name),
    )
    monkeypatch.setattr(runtime.event_worker, "start", lambda: None)

    runtime.start()

    assert created_tables == ["frames", connection.event_name]


def test_connection_database_still_enables_stream_during_migration() -> None:
    connection = Connection(
        "distance",
        "hcsr04",
        {"trig": "4", "echo": "5"},
        database=_database(),
    )

    assert connection.stream_enabled is True


def test_database_runtime_rejects_writes_to_unknown_tables() -> None:
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        event_worker=EventWorker(),
    )

    runtime.write_database_table("missing", [])
    with pytest.raises(RuntimeError, match="not registered"):
        runtime.write_database_table("missing", [{"value": "1"}])
