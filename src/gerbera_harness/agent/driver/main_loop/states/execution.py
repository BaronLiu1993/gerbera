from dataclasses import dataclass
from typing import ClassVar

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    InitialistationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecutionEventSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import (
    build_valid_schema,
)


@dataclass(frozen=True)
class Execution(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.EXECUTION
    prompt_file: ClassVar[str] = "EXECUTION.md"
    valid_decisions: ClassVar[
        frozenset[InitialistationDecisionEnum]
    ] = frozenset(
        {
            InitialistationDecisionEnum.ACCEPTED,
            InitialistationDecisionEnum.REJECTED,
        }
    )
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.EXECUTION, LoopStateEnum.REVIEW}
    )
    # Execute emits events indicating whether each action worked.
    valid_schema: ClassVar[dict] = build_valid_schema(
        valid_transition_states,
        ExecutionEventSchema,
    )
