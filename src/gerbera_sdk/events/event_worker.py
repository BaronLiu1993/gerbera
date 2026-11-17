import threading
from dataclasses import dataclass, field
from queue import Empty, Queue

from gerbera_sdk.events.event_schema import WriteJob
from gerbera_sdk.database_runtime import DatabaseRuntime

QUEUE_WAIT_SECONDS = 0.5

@dataclass
class EventWorker:
    database: DatabaseRuntime
    queue: Queue[WriteJob] = field(
        default_factory=Queue,
        init=False,
        repr=False,
    )
    stop_event: threading.Event = field(
        default_factory=threading.Event,
        init=False,
    )
    thread: threading.Thread = field(default=None, init=False)

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                job = self.queue.get(timeout=QUEUE_WAIT_SECONDS)
            except Empty:
                continue

            try:
                self.database.write_batch(job.table_name, job.batch)
            except Exception as error:
                self.stop_event.set()
                raise ValueError(f"Failed to write to database {error}")
            finally:
                self.queue.task_done()

    def start(self) -> None:
        if self.thread is not None:
            raise RuntimeError("EventWorker is already running")

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self.run,
            daemon=False,
            name="gerbera-event-worker",
        )
        try:
            self.thread.start()
        except RuntimeError:
            self.thread = None
            raise

    def stop(self, timeout: float = 2.0) -> None:
        if self.thread is None:
            return
        self.stop_event.set()
        self.thread.join(timeout=timeout)
        self.thread = None

    def write_to_db(self, table_name: str, batch: list[dict[str, str]]) -> None:
        if not batch:
            return
        
        job = WriteJob(
            table_name=table_name,
            batch=[dict(row) for row in batch],
        )
        self.queue.put(job)
