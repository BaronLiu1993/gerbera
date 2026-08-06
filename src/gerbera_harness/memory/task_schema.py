import uuid
from typing import Literal

from pydantic import Field

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class TaskSchema(StrictSchema):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: Literal["pending", "in_progress", "completed", "failed"]
    task: ExecuteActionGroupSchema
