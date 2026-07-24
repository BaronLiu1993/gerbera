from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    ReviewSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import StrictSchema


ActionUnionType = (
    ContinuousExecuteSchema | DiscreteExecuteSchema | ReviewSchema
)


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[ActionUnionType]
