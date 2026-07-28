from pydantic import BaseModel, ConfigDict, Field


class EventKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(min_length=1)
    microcontroller_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
