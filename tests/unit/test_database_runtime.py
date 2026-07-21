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


def test_database_runtime_rejects_unsupported_streaming_component() -> None:
    connection = Connection(
        "led",
        "led",
        {"out": "13"},
        microcontroller_id="board-1",
        database=_database(),
    )
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(
            microcontrollers=[SimpleNamespace(connections=[connection])]
        ),
        event_worker=EventWorker(),
    )

    with pytest.raises(ValueError, match="does not support database streaming"):
        runtime.start()


def test_database_runtime_rejects_writes_to_unknown_tables() -> None:
    runtime = DatabaseRuntime(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        event_worker=EventWorker(),
    )

    runtime.write_database_table("missing", [])
    with pytest.raises(RuntimeError, match="not registered"):
        runtime.write_database_table("missing", [{"value": "1"}])
