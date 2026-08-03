from typing import Literal

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class TaskSchema(StrictSchema):
    status: Literal["in_progress", "completed", "failed"]
    task: ExecuteActionGroupSchema
