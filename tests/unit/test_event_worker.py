import threading

import pytest

from gerbera_sdk.events.event_worker import EventWorker


class BlockingWriter:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.payloads: list[list[dict[str, str]]] = []

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        self.started.set()
        self.release.wait(timeout=1)
        self.payloads.append(payload)


def test_wait_until_idle_waits_for_active_database_write() -> None:
    writer = BlockingWriter()
    worker = EventWorker(retry_delay_seconds=0)
    worker.configure_writer(writer)
    worker.start()
    worker.write_to_db("sensor_readings", [{"value": "1"}])
    assert writer.started.wait(timeout=1)

    wait_completed = threading.Event()
    wait_thread = threading.Thread(
        target=lambda: (
            worker.wait_until_idle(),
            wait_completed.set(),
        )
    )
    wait_thread.start()

    assert not wait_completed.wait(timeout=0.05)
    writer.release.set()
    assert wait_completed.wait(timeout=1)

    wait_thread.join(timeout=1)
    worker.stop()
    assert worker._thread is None
    assert writer.payloads == [[{"value": "1"}]]


class FailingWriter:
    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        raise OSError("database unavailable")


def test_wait_until_idle_surfaces_database_write_failure() -> None:
    worker = EventWorker(max_retries=0, retry_delay_seconds=0)
    worker.configure_writer(FailingWriter())
    worker.start()
    worker.write_to_db("sensor_readings", [{"value": "1"}])

    with pytest.raises(
        RuntimeError,
        match="EventWorker database write failed",
    ):
        worker.wait_until_idle()

    worker.stop()
