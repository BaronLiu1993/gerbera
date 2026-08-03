from datetime import datetime
from typing import Literal

from pydantic import JsonValue

from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class EventSchema(StrictSchema):
    event_type: Literal["tool_call", "plan_action", "revise_plan"]
    event_name: str
    event_description: str
    event_status: Literal["success", "failed", "timed_out"]
    occurred_at: datetime
    result: JsonValue | None = None
