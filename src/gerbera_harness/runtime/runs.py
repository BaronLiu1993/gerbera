import asyncio
from collections import deque
from dataclasses import dataclass, field

from gerbera_harness.runtime.harness import BaseHarness
from gerbera_harness.runtime.state_machine.bindings import (
    enforce_json_limit, validate_document,
)
from gerbera_harness.runtime.state_machine.engine import WorkflowExecution
from gerbera_harness.runtime.state_machine.schemas import (
    RunRequest, RunStatus, WorkflowEvent,
)


class RunCapacityError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunLimits:
    maximum_runs: int = 100
    maximum_active_runs: int = 8
    events_per_run: int = 1000
    maximum_request_bytes: int = 64_000


@dataclass
class RunRecord:
    execution: WorkflowExecution
    events: deque[WorkflowEvent]
    task: asyncio.Task | None = None

    async def record_event(self, event: WorkflowEvent) -> None:
        self.events.append(event)

    def snapshot(self) -> dict:
        result = self.execution.result
        if result is not None:
            return result.model_dump(mode="json")
        state = self.execution.state
        return {
            "run_id": state.run_id,
            "workflow": state.workflow,
            "status": state.status,
            "current_node": state.current_node,
            "step": state.step,
        }


@dataclass
class RunManager:
    harness: BaseHarness
    limits: RunLimits = field(default_factory=RunLimits)
    runs: dict[str, RunRecord] = field(default_factory=dict, init=False)

    def start(self, request: RunRequest) -> RunRecord:
        enforce_json_limit(request.model_dump(mode="json"), self.limits.maximum_request_bytes)
        pending_events = deque(maxlen=self.limits.events_per_run)

        async def record_event(event: WorkflowEvent) -> None:
            pending_events.append(event)

        execution = self.harness.create_execution(request, record_event)
        definition = execution.workflow.definition
        validate_document(request.input, definition.interface.input_schema)
        self.reserve_capacity()
        record = RunRecord(execution, pending_events)
        self.runs[execution.state.run_id] = record
        record.task = asyncio.create_task(execution.run())
        return record

    def reserve_capacity(self) -> None:
        active = sum(record.execution.result is None for record in self.runs.values())
        if active >= self.limits.maximum_active_runs:
            raise RunCapacityError("Active run limit reached")
        if len(self.runs) < self.limits.maximum_runs:
            return
        for run_id, record in self.runs.items():
            if record.execution.result is not None:
                del self.runs[run_id]
                return
        raise RunCapacityError("Run retention limit reached")

    def get(self, run_id: str) -> RunRecord:
        try:
            return self.runs[run_id]
        except KeyError as error:
            raise KeyError("Run not found") from error

    def cancel(self, run_id: str) -> RunRecord:
        record = self.get(run_id)
        if record.execution.result is not None:
            return record
        state = record.execution.state
        record.execution.state = state.model_copy(update={"status": RunStatus.CANCELLING})
        record.execution.cancellation_requested = True
        if record.task is not None and state.started_at is not None:
            record.task.cancel()
        return record

    async def close(self) -> None:
        tasks = []
        for run_id, record in self.runs.items():
            if record.execution.result is None:
                self.cancel(run_id)
            if record.task is not None:
                tasks.append(record.task)
        await asyncio.gather(*tasks, return_exceptions=True)
