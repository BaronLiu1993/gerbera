from typing import Annotated

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass


@dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", validate_default=True))
class Pin:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    value: Annotated[str, Field(min_length=1, pattern=r"\S")]
