import math
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from gerbera_sdk.utils import StrictSchema


class NumericRange(StrictSchema):
    model_config = ConfigDict(frozen=True)

    kind: Literal['range']
    minimum: float | None
    maximum: float | None

    @model_validator(mode='after')
    def validate_limits(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Parameter minimum cannot exceed maximum')
        return self

    def validate_value(self, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError('Parameter must be finite')
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f'Parameter must be >= {self.minimum}')
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f'Parameter must be <= {self.maximum}')
        return value

    def json_constraints(self) -> dict:
        return {key: value for key, value in self.model_dump().items() if key != 'kind' and value is not None}


class IntegerRange(NumericRange):
    kind: Literal['integer_range']
    minimum: int | None
    maximum: int | None

    def validate_value(self, value: float) -> float:
        super().validate_value(value)
        if not float(value).is_integer():
            raise ValueError('Parameter must be an integer')
        return value

    def json_constraints(self) -> dict:
        return super().json_constraints() | {'type': 'integer'}


class NumericChoice(StrictSchema):
    model_config = ConfigDict(frozen=True)

    kind: Literal['choice']
    values: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_choices(self):
        if len(set(self.values)) != len(self.values):
            raise ValueError('Duplicate parameter choice')
        return self

    def validate_value(self, value: float) -> float:
        if value not in self.values:
            raise ValueError(f'Parameter must be one of {self.values}')
        return value

    def json_constraints(self) -> dict:
        return {'enum': list(self.values)}


ParameterDomain = Annotated[NumericRange | IntegerRange | NumericChoice, Field(discriminator='kind')]
