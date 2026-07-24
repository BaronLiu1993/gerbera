from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.step_schema import (
    StepSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import StrictSchema


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[StepSchema]
