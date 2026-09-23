from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


class FakeDatabase(Database):
    def __init__(self) -> None:
        self.batches = []

        super().__init__("localhost", 5432, "user", "password", "gerbera")

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        self.batches.append(list(payload))


def test_stream_payload_is_buffered_and_written(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    database = FakeDatabase()
    board = Microcontroller(
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        connections=[
            Connection(
                "sensor",
                "hw201",
                {"out": "7"},
                "Infrared sensor",
                microcontroller_id="board-1",
                stream=True,
            )
        ],
    )
    worker = EventWorker(database=database, retry_delay_seconds=0)

    worker.start()
    table_name = board.connections[0].event_name
    buffer = Buffer(table_name=table_name, event_worker=worker)
    event = Event(
        "STREAM",
        board.id,
        table_name,
        board.connections[0].name,
        board.connections[0].component_type,
        streamable=True,
        table_name=table_name,
        buffer=buffer,
        event_key=table_name,
        latest_val=None,
    )
    event.perform_work({"value": "1"})
    event.flush()
    worker.stop()

    assert len(database.batches) == 1
    assert event.latest_val == {"value": "1"}
    assert database.batches[0][0]["value"] == "1"
    assert "created_at" in database.batches[0][0]
