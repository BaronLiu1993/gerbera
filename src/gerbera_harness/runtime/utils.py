from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

SnakeCaseVariable = Annotated[
    str,
    Field(
        pattern=SNAKE_CASE_PATTERN,
        description="Lowercase snake_case variable name.",
    ),
]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
