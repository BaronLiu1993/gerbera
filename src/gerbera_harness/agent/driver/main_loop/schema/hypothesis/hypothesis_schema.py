from gerbera_harness.agent.driver.main_loop.schema.initialisation.clarification_schema import (
    QuestionSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    MethodSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import (
    SnakeCaseVariable,
    StrictSchema,
)


class HypothesisSchema(StrictSchema):
    hypothesis: str
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    controlled_variables: list[SnakeCaseVariable]
    assumptions: list[str]
    method: MethodSchema
