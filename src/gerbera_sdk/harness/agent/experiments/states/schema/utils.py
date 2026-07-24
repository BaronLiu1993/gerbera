from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


# Snake Case Enforcement
SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

SnakeCaseVariable = Annotated[
    str,
    Field(
        pattern=SNAKE_CASE_PATTERN,
        description="Lowercase snake_case variable name.",
    ),
]

# Strict Schema
class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
