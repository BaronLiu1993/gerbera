from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, TypeAdapter

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


JsonScalar: TypeAlias = str | int | float | bool | None
ObservationPayload: TypeAlias = Annotated[
    "ObservationToolCallSchema | ObservationResultSchema",
    Field(discriminator="content_type"),
]


class ObservationStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"
    COMPLETE = "complete"


class ObservationToolCallSchema(StrictSchema):
    content_type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, JsonScalar]


class ObservationResultSchema(StrictSchema):
    content_type: Literal["finish"]
    reason: str
    summary: str
    result: dict[str, JsonScalar]


class ObservationResponseSchema(StrictSchema):
    observation: ObservationPayload


class ObservationReviewSchema(StrictSchema):
    status: ObservationStatusEnum
    feedback: str


observation_adapter = TypeAdapter(ObservationResponseSchema)
observation_review_adapter = TypeAdapter(ObservationReviewSchema)
