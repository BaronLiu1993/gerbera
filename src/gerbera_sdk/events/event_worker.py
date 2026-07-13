from dataclasses import dataclass
from queue import Empty, Queue
import threading
import time

from gerbera_sdk.models.database import Database


@dataclass(frozen=True)
class WriteJob:
    table_name: str
    batch: list[dict[str, str]]
    retry_count: int = 0


class EventWorker:
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self._database: Database | None = None
        self._queue: Queue[WriteJob] = Queue()
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._thread: threading.Thread | None = None
        self._running = False

    def configure_database(self, database: Database) -> None:
        self._database = database

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
        if self._database is None:
            raise RuntimeError("EventWorker database is not configured")

        try:
            self._database.write_database_table(job.table_name, job.batch)
        except Exception:
            if job.retry_count >= self._max_retries:
                raise

            time.sleep(self._retry_delay_seconds)
            self._queue.put(
                WriteJob(
                    table_name=job.table_name,
                    batch=job.batch,
                    retry_count=job.retry_count + 1,
                )
            )


event_worker = EventWorker()
