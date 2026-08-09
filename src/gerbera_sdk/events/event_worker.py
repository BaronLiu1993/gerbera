from dataclasses import dataclass, field
from queue import Empty, Queue
import threading
import time
from typing import Protocol
import uuid



@dataclass(frozen=True)
class WriteJob:
    table_name: str
    batch: list[dict[str, str]]
    retry_count: int = 0


@dataclass
class EventWorker:
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    _writer: DatabaseWriter | None = field(default=None, init=False, repr=False)
    _queue: Queue[WriteJob] = field(
        default_factory=Queue,
        init=False,
        repr=False,
    )
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(
        default_factory=threading.Event,
        init=False,
        repr=False,
    )
    _error: Exception | None = field(default=None, init=False, repr=False)
    _error_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def configure_writer(self, writer: DatabaseWriter) -> None:
        self._writer = writer

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        with self._error_lock:
            self._error = None

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=False,
            name="gerbera-event-worker",
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is None:
            return

        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError("EventWorker thread did not stop")

        self._thread = None

    def write_to_db(
        self,
        table_name: str,
        batch: list[dict[str, str]],
    ) -> None:
        if not batch:
            return

        self._queue.put(
            WriteJob(
                table_name=table_name,
                batch=[dict(item) for item in batch],
            )
        )

    def flush_now(self) -> None:
        while not self._queue.empty():
            try:
                job = self._queue.get_nowait()
            except Empty:
                break

            try:
                self._process_job(job)
            except Exception as exc:
                self._record_error(exc)
            finally:
                self._queue.task_done()

        self._raise_if_failed()

    def wait_until_idle(self) -> None:
        self._queue.join()
        self._raise_if_failed()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                continue

            try:
                self._process_job(job)
            except Exception as exc:
                self._record_error(exc)
            finally:
                self._queue.task_done()

    def _record_error(self, error: Exception) -> None:
        with self._error_lock:
            if self._error is None:
                self._error = error

    def _raise_if_failed(self) -> None:
        with self._error_lock:
            error = self._error

        if error is not None:
            raise RuntimeError("EventWorker database write failed") from error

    def _process_job(self, job: WriteJob) -> None:
        if self._writer is None:
            raise RuntimeError("EventWorker database writer is not configured")

        try:
            self._writer.write_database_table(job.table_name, job.batch)
        except Exception:
            if job.retry_count >= self.max_retries:
                raise

            time.sleep(self.retry_delay_seconds)
            self._queue.put(
                WriteJob(
                    table_name=job.table_name,
                    batch=job.batch,
                    retry_count=job.retry_count + 1,
                )
            )
