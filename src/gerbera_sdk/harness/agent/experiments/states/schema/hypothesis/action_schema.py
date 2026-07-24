from enum import Enum

from gerbera_sdk.harness.agent.experiments.states.schema.utils import (
    SnakeCaseVariable,
    StrictSchema,
)


# class ActionTypeEnum(str, Enum):
#     EXECUTE = "execute"
#     OBSERVE = "observe"
#     REVIEW = "review"


# class ActionParameterSchema(StrictSchema):
#     variable: SnakeCaseVariable
#     value: bool | int | float | str


# class ActionSchema(StrictSchema):
#     type: ActionTypeEnum
#     target: str
#     params: list[ActionParameterSchema]
