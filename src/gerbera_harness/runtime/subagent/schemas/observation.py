from enum import Enum
from typing import Literal

from pydantic import TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema, JsonScalar


class ObservationStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"
    COMPLETE = "complete"


class ObservationValueSchema(HarnessSchema):
    key: str
    value: JsonScalar


class ObservationToolCallSchema(HarnessSchema):
    content_type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, JsonScalar]


class ObservationResultSchema(HarnessSchema):
    content_type: Literal["finish"]
    reason: str
    summary: str
    result: dict[str, JsonScalar]


class ObservationResponseSchema(HarnessSchema):
    content_type: Literal["tool_call", "finish"]
    tool_name: str | None
    arguments: list[ObservationValueSchema]
    reason: str | None
    summary: str | None
    result: list[ObservationValueSchema]


class ObservationReviewSchema(HarnessSchema):
    status: ObservationStatusEnum
    feedback: str


observation_adapter = TypeAdapter(ObservationResponseSchema)
observation_review_adapter = TypeAdapter(ObservationReviewSchema)
