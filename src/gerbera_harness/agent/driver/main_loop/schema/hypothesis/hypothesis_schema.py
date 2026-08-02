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
    # TODO(physical-constraints): Add typed physical_constraints and
    # required_observations fields. Keep static safety/capability constraints
    # separate from dynamic world state, and enforce hard constraints in the
    # action runtime rather than relying on assumptions or prompt compliance.
    assumptions: list[str]
    method: MethodSchema
