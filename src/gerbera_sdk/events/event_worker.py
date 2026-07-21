from dataclasses import dataclass, field
from queue import Empty, Queue
import threading
import time
from typing import Protocol
import uuid


class DatabaseWriter(Protocol):
    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None: ...


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
    _running: bool = field(default=False, init=False, repr=False)

    def configure_writer(self, writer: DatabaseWriter) -> None:
        self._writer = writer

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="gerbera-event-worker",
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)

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
                return

            self._process_job(job)
            self._queue.task_done()

    def _run(self) -> None:
        while self._running:
            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                continue

            self._process_job(job)
            self._queue.task_done()

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
