import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field

from gerbera_harness.runtime.schemas.execute import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.runtime.schemas.base import HarnessSchema


class ToolStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ToolSchema(HarnessSchema):
    session_id: str
    action: DiscreteExecuteSchema | ContinuousExecuteSchema
    tool_status: ToolStatusEnum
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tool_call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskSchema(HarnessSchema):
    task_goal: str
    success_criteria: list[str] = Field(default_factory=list)
    status: TaskStatusEnum
    session_id: str
    attempts: int = 0
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_calls: list[ToolSchema] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskStateSchema(HarnessSchema):
    user_intent: str
    goal: str
    success_criteria: list[str] = Field(default_factory=list)
    tasks: list[TaskSchema] = Field(default_factory=list)
    current_task_id: str
