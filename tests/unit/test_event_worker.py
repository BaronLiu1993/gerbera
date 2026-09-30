import threading

import pytest

from gerbera_sdk.events.event_worker import EventWorker, WriteJob


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
    database = BlockingWriter()
    worker = EventWorker(database=database, retry_delay_seconds=0)
    worker.start()
    worker.write_to_db("sensor_readings", [{"value": "1"}])
    assert database.started.wait(timeout=1)

    wait_completed = threading.Event()
    wait_thread = threading.Thread(
        target=lambda: (
            worker.wait_until_idle(),
            wait_completed.set(),
        )
    )
    wait_thread.start()

    assert not wait_completed.wait(timeout=0.05)
    database.release.set()
    assert wait_completed.wait(timeout=1)

    wait_thread.join(timeout=1)
    worker.stop()
    assert worker.thread is None
    assert database.payloads == [[{"value": "1"}]]


class FailingWriter:
    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        raise OSError("database unavailable")


def test_process_job_surfaces_database_write_failure() -> None:
    worker = EventWorker(
        database=FailingWriter(),
        max_retries=0,
        retry_delay_seconds=0,
    )

    with pytest.raises(RuntimeError, match="Database write failed") as error:
        worker.process_job(
            WriteJob("sensor_readings", [{"value": "1"}])
        )

    assert isinstance(error.value.__cause__, OSError)


class SelectiveWriter:
    def __init__(self) -> None:
        self.written_tables: list[str] = []

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        if table_name == "broken":
            raise OSError("database unavailable")
        self.written_tables.append(table_name)


def test_terminal_write_failure_does_not_strand_later_jobs() -> None:
    database = SelectiveWriter()
    worker = EventWorker(
        database=database,
        max_retries=0,
        retry_delay_seconds=0,
    )
    worker.start()
    worker.write_to_db("broken", [{"value": "1"}])
    worker.write_to_db("healthy", [{"value": "2"}])

    with pytest.raises(RuntimeError, match="broken"):
        worker.wait_until_idle()

    assert database.written_tables == ["healthy"]
    assert worker.thread is not None
    assert worker.thread.is_alive()
    worker.stop()


class RetryWriter:
    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}
        self.healthy_written = threading.Event()

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        self.attempts[table_name] = self.attempts.get(table_name, 0) + 1
        if table_name == "retry" and self.attempts[table_name] == 1:
            raise OSError("retry once")
        if table_name == "healthy":
            self.healthy_written.set()


def test_retry_delay_does_not_block_later_jobs() -> None:
    database = RetryWriter()
    worker = EventWorker(
        database=database,
        max_retries=1,
        retry_delay_seconds=0.2,
    )
    worker.start()
    worker.write_to_db("retry", [{"value": "1"}])
    worker.write_to_db("healthy", [{"value": "2"}])

    assert database.healthy_written.wait(timeout=0.1)
    worker.wait_until_idle()
    worker.stop()

    assert database.attempts == {"retry": 2, "healthy": 1}
