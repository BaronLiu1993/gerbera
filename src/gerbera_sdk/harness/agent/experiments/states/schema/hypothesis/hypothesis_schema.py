from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.method_schema import (
    MethodSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import (
    SnakeCaseVariable,
    StrictSchema,
)


class HypothesisSchema(StrictSchema):
    hypothesis: str
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    controlled_variables: list[SnakeCaseVariable]
    assumptions: list[str]
    methods: list[MethodSchema]
