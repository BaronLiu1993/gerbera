from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Queue
import threading
import time
import uuid

from gerbera_sdk.models.hardware.database import Database


@dataclass(frozen=True)
class WriteJob:
    table_name: str
    batch: list[dict[str, str]]
    retry_count: int = 0


@dataclass
class EventWorker:
    database: Database
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    queue: Queue[WriteJob] = field(
        default_factory=Queue,
        init=False,
        repr=False,
    )
    stop_event: threading.Event | None = None
    thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread is not None:
            raise RuntimeError("EventWorker is already running")

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self.run,
            daemon=False,
            name="gerbera-event-worker",
        )
        self.stop_event = stop_event
        self.thread = thread

        try:
            thread.start()
        except RuntimeError:
            self.stop_event = None
            self.thread = None
            raise

    def stop(self, timeout: float = 2.0) -> None:
        stop_event = self.stop_event
        thread = self.thread
        if stop_event is None or thread is None:
            return

        stop_event.set()
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError("EventWorker thread did not stop")

        self.stop_event = None
        self.thread = None

    def run(self) -> None:
        stop_event = self.stop_event
        if stop_event is None:
            raise RuntimeError("EventWorker is not running")

        while not stop_event.is_set():
            try:
                job = self.queue.get(timeout=0.5)
            except Empty:
                continue

            try:
                self.process_job(job)
            finally:
                self.queue.task_done()

    def write_to_db(
        self,
        table_name: str,
        batch: list[dict[str, str]],
    ) -> None:
        if not batch:
            return

        self.queue.put(
            WriteJob(
                table_name=table_name,
                batch=[dict(item) for item in batch],
            )
        )

    def process_job(self, job: WriteJob) -> None:
        try:
            self.database.write_database_table(job.table_name, job.batch)
        except Exception:
            if job.retry_count >= self.max_retries:
                raise RuntimeError("Failed to Write to Database")

            time.sleep(self.retry_delay_seconds)
            self.queue.put(
                WriteJob(
                    table_name=job.table_name,
                    batch=job.batch,
                    retry_count=job.retry_count + 1,
                )
            )

    def wait_until_idle(self) -> None:
        self.queue.join()
