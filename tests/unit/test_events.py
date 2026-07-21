from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker, WriteJob


@pytest.mark.parametrize(
    ("table_name", "worker", "message"),
    [
        (None, EventWorker(), "table_name"),
        ("readings", None, "event_worker"),
    ],
)
def test_stream_event_requires_its_dependencies(
    table_name: str | None,
    worker: EventWorker | None,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        Event(
            event_type="STREAM",
            microcontroller_id="board-1",
            event_name="sensor",
            streamable=True,
            table_name=table_name,
            event_worker=worker,
        )


def test_event_bus_rejects_duplicate_and_missing_events() -> None:
    event_bus = EventBus()
    event = Event("MCP", "board-1", "sensor")
    event_bus.add_event("MCP", "board-1", "sensor", event)

    with pytest.raises(RuntimeError, match="already exists"):
        event_bus.add_event("MCP", "board-1", "sensor", event)

    with pytest.raises(RuntimeError, match="does not exist"):
        event_bus.get_handler(("MCP", "board-1", "missing"))


def test_event_worker_requeues_a_failed_write_until_retry_limit() -> None:
    class FailingWriter:
        def write_database_table(self, table_name, payload) -> None:
            raise OSError("database unavailable")

    worker = EventWorker(max_retries=1, retry_delay_seconds=0)
    worker.configure_writer(FailingWriter())

    worker._process_job(WriteJob("readings", [{"value": "1"}]))
    retry = worker._queue.get_nowait()
    assert retry.retry_count == 1

    with pytest.raises(OSError, match="database unavailable"):
        worker._process_job(retry)


def test_listener_rejects_duplicate_payload_keys() -> None:
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        _serial_pool={},
        _threads={},
        _event_bus=EventBus(),
    )

    assert listener._parse_payload("invalid") is None
    with pytest.raises(ValueError, match="Key already exists"):
        listener._parse_payload("MCP,sensor,value:1,value:2")


def test_listener_joins_threads_even_when_transport_shutdown_fails() -> None:
    class FailingConnection:
        def destroy(self) -> None:
            raise OSError("close failed")

    class Thread:
        joined = False

        def join(self, timeout: float) -> None:
            self.joined = True

    thread = Thread()
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        _serial_pool={"board-1": FailingConnection()},
        _threads={"board-1": thread},
        _event_bus=EventBus(),
    )

    with pytest.raises(OSError, match="close failed"):
        listener.stop_listeners()

    assert thread.joined is True
    assert listener._threads == {}
