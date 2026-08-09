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
    thread: threading.Thread | None = field(default=None, init=False, repr=False)
    stop_event: threading.Event = field(
        default_factory=threading.Event,
        init=False,
        repr=False,
    )

    # Turn on and off the worker thread
    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self.run,
            daemon=False,
            name="gerbera-event-worker",
        )
        self.thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        if self._thread is None:
            return
        self.stop_event.set()

        self.thread.join(timeout=timeout)
        if self.thread.is_alive():
            raise RuntimeError("EventWorker thread did not stop")

        self._thread = None

    # Function that works on another thread and continually checks the queue and then processes it
    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                job = self.queue.get(timeout=0.5)
            except Empty:
                continue

            try:
                self.process_job(job)
            finally:
                self.queue.task_done()

    # Actual function that puts new write jobs into the queue
    def insert_into_queue(
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

    # Actual method that writes to database
    def process_job(self, job: WriteJob) -> None:
        try:
            self.database.write_database_table(job.table_name, job.batch)
        except Exception:
            if job.retry_count >= self.max_retries:
                raise RuntimeError("Failed to Write to Database")

            # Put it back into the queue
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
