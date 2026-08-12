import uuid
from enum import Enum

from pydantic import Field

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskSchema(StrictSchema):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatusEnum
    task: ExecuteActionGroupSchema
