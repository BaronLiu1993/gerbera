from datetime import datetime

from pydantic import JsonValue

from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class WorldStateSchema(StrictSchema):
    observed_at: datetime
    state: dict[str, JsonValue]
