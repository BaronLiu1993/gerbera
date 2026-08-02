from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema
from pydantic import JsonValue
from typing import Literal

from datetime import datetime

class EventSchema(StrictSchema):
    event_type: Literal["tool_call", "plan_action", "revise_plan"]
    event_name: str # For planning it is just agent plan for, revise or it is the tool name it self
    event_description: str
    event_status: Literal["success", "failed"]
    occurred_at: datetime
    result: JsonValue | None = None