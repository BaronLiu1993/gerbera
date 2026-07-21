from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime


class FakeCursor:
    def __init__(self) -> None:
        self.executed = []
        self.batches = []

    def execute(self, query) -> None:
        self.executed.append(query)

    def executemany(self, query, payload) -> None:
        self.batches.append(list(payload))

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass


class FakeDatabaseConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass


def test_stream_payload_is_provisioned_buffered_and_written(
    device_registry,
    monkeypatch,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    database = Database("localhost", 5432, "user", "password", "gerbera")
    board = Microcontroller(port="/dev/board-1", fqbn="arduino:avr:uno")
    board.add_connections(
        [
            Connection(
                "sensor",
                "hw201",
                {"out": "7"},
                database=database,
            )
        ]
    )
    hardware_system = HardwareSystem(microcontrollers=[board])
    cursor = FakeCursor()
    monkeypatch.setattr(
        "gerbera_sdk.models.runtime.database_runtime.psycopg.connect",
        lambda dsn: FakeDatabaseConnection(cursor),
    )
    worker = EventWorker(retry_delay_seconds=0)
    runtime = DatabaseRuntime(hardware_system, worker)

    runtime.start()
    table_name = board.connections[0].event_name
    event = Event(
        "STREAM",
        board.id,
        table_name,
        streamable=True,
        table_name=table_name,
        event_worker=worker,
    )
    event.perform_work({"value": "1"})
    event.flush()
    runtime.stop()

    assert table_name in database.table_names
    assert cursor.executed
    assert len(cursor.batches) == 1
    assert cursor.batches[0][0]["value"] == "1"
    assert "created_at" in cursor.batches[0][0]
