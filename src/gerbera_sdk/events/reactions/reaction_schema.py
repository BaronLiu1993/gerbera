from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    JsonValue,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

ReactionValue = StrictBool | StrictInt | FiniteFloat | StrictStr


class ReactionOperator(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    LESS_THAN_EQUAL = "less_than_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_EQUAL = "greater_than_equal"


class ReactionTriggerMode(str, Enum):
    ONCE = "once"
    CONTINUOUS = "continuous"


class ReactionEventSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["MCP", "STREAM"]
    microcontroller_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    payload_field: str = Field(min_length=1)

    @property
    def event_key(self) -> tuple[str, str, str]:
        return (
            self.event_type,
            self.microcontroller_id,
            self.event_name,
        )


class ReactionConditionSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: ReactionOperator
    expected_value: ReactionValue

    @model_validator(mode="after")
    def validate_ordered_value(self) -> "ReactionConditionSchema":
        ordered_operators = {
            ReactionOperator.LESS_THAN,
            ReactionOperator.LESS_THAN_EQUAL,
            ReactionOperator.GREATER_THAN,
            ReactionOperator.GREATER_THAN_EQUAL,
        }
        if self.operator in ordered_operators and isinstance(
            self.expected_value,
            (bool, str),
        ):
            raise ValueError("Ordered reaction comparisons require a number")
        return self


class ReactionActionSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class CreateReactionSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: ReactionEventSchema
    condition: ReactionConditionSchema
    action: ReactionActionSchema
    trigger_mode: ReactionTriggerMode
    cooldown_seconds: FiniteFloat = Field(default=0, ge=0)


class ReactionDefinitionSchema(CreateReactionSchema):
    schema_version: Literal[1] = 1
    reaction_id: UUID
    created_at: datetime


class ReactionRuntimeSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    latest_value: ReactionValue | None = None
    trigger_count: int = Field(default=0, ge=0)
    last_triggered_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_result: JsonValue | None = None
    last_error: str | None = None


class ReactionSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    definition: ReactionDefinitionSchema
    runtime: ReactionRuntimeSchema


class DeleteReactionSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reaction_id: UUID


class DeleteReactionResultSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    deleted: ReactionDefinitionSchema
