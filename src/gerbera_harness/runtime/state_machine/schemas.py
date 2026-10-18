from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ReservedNode(StrEnum):
    ENTRY = "__entry__"
    EXIT = "__exit__"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


TerminalStatus = Literal[
    RunStatus.SUCCEEDED, RunStatus.FAILED,
    RunStatus.CANCELLED, RunStatus.TIMED_OUT,
]


class RunRequest(WorkflowSchema):
    workflow: str = Field(min_length=1)
    input: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class WorkflowError(WorkflowSchema):
    code: str
    message: str
    retryable: bool = False


class WorkflowState(WorkflowSchema):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow: str
    status: RunStatus = RunStatus.PENDING
    current_node: str = ReservedNode.ENTRY
    step: int = 0
    input: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    values: dict[str, JsonValue] = Field(default_factory=dict)
    nodes: dict[str, JsonValue] = Field(default_factory=dict)
    started_at: datetime | None = None


class RunResult(WorkflowSchema):
    run_id: str
    workflow: str
    status: TerminalStatus
    current_node: Literal[ReservedNode.EXIT] = ReservedNode.EXIT
    output: JsonValue = None
    error: WorkflowError | None = None
    source_node: str
    steps: int
    started_at: datetime
    completed_at: datetime = Field(default_factory=utc_now)


class NodeResult(WorkflowSchema):
    outcome: str = Field(min_length=1)
    output: JsonValue = None


class ExecutionLimits(WorkflowSchema):
    timeout_seconds: float = Field(default=120, gt=0)
    maximum_attempts: int = Field(default=1, ge=1, le=10)


class WorkflowLimits(WorkflowSchema):
    maximum_steps: int = Field(default=100, ge=1)
    maximum_duration_seconds: float = Field(default=3600, gt=0)
    maximum_state_bytes: int = Field(default=1_000_000, ge=1024)


class NodeDefinition(WorkflowSchema):
    schema_version: Literal["1"] = "1"
    type: str = Field(min_length=1)
    config: dict[str, JsonValue] = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    outcomes: tuple[str, ...] = Field(min_length=1)
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)


class TerminalDefinition(WorkflowSchema):
    status: TerminalStatus
    output: dict[str, str] = Field(default_factory=dict)
    error: WorkflowError | None = None


class Transition(WorkflowSchema):
    source: str = Field(alias="from")
    outcome: str
    destination: str = Field(alias="to")
    terminal: TerminalDefinition | None = None


class WorkflowInterface(WorkflowSchema):
    input_schema: dict[str, JsonValue] = Field(
        default_factory=lambda: {"type": "object"}
    )
    output_schema: dict[str, JsonValue] = Field(
        default_factory=lambda: {"type": "object"}
    )


class WorkflowDefinition(WorkflowSchema):
    schema_version: Literal["1"] = "1"
    name: str = Field(min_length=1)
    interface: WorkflowInterface = Field(default_factory=WorkflowInterface)
    nodes: dict[str, NodeDefinition]
    transitions: tuple[Transition, ...]
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)


class WorkflowEvent(WorkflowSchema):
    id: int
    run_id: str
    type: str
    timestamp: datetime = Field(default_factory=utc_now)
    node: str | None = None
    workflow: str | None = None
    data: dict[str, JsonValue] = Field(default_factory=dict)
