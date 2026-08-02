from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


class ObservationStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"


class ObservationToolCallSchema(StrictSchema):
    content_type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, object]


class ObservationFinishSchema(StrictSchema):
    content_type: Literal["finish"]
    reason: str


Observation = Annotated[
    ObservationToolCallSchema | ObservationFinishSchema,
    Field(discriminator="content_type"),
]


class ObservationResponseSchema(StrictSchema):
    observation: Observation


class ObservationReviewSchema(StrictSchema):
    status: ObservationStatusEnum
    feedback: str


observation_adapter = TypeAdapter(ObservationResponseSchema)
observation_review_adapter = TypeAdapter(ObservationReviewSchema)
