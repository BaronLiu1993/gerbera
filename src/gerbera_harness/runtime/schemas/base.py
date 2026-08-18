from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None


SNAKE_CASE_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

SnakeCaseIdentifier = Annotated[
    str,
    Field(
        pattern=SNAKE_CASE_IDENTIFIER_PATTERN,
        description="Lowercase snake_case identifier.",
    ),
]


class HarnessSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
