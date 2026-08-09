import pytest

from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime


def _database() -> Database:
    return Database("localhost", 5432, "user", "password", "gerbera")


def test_database_runtime_starts_worker() -> None:
    class Worker(EventWorker):
        started = False

        def start(self) -> None:
            self.started = True

    worker = Worker()
    runtime = DatabaseRuntime(
        event_worker=worker,
        database=_database(),
    )

    runtime.start()

    assert worker.started is True
    assert worker._writer is runtime


def test_connection_database_still_enables_stream_during_migration() -> None:
    connection = Connection(
        "distance",
        "hcsr04",
        {"trig": "4", "echo": "5"},
        database=_database(),
    )

    assert connection.stream_enabled is True


def test_database_runtime_rejects_empty_writes() -> None:
    runtime = DatabaseRuntime(
        event_worker=EventWorker(),
        database=_database(),
    )

    with pytest.raises(ValueError, match="payload is empty"):
        runtime.write_database_table("readings", [])
