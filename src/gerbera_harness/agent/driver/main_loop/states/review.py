from dataclasses import dataclass
from typing import ClassVar

from pydantic import RootModel

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExperimentState,
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import (
    build_valid_schema,
)


@dataclass(frozen=True)
class Review(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.REVIEW
    prompt_file: ClassVar[str] = "REVIEW.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {
            LoopStateEnum.EXECUTION,
            LoopStateEnum.REVIEW,
        }
    )
    valid_decisions: ClassVar[
        frozenset[InitialisationDecisionEnum]
    ] = frozenset(
        {
            InitialisationDecisionEnum.ACCEPTED,
            InitialisationDecisionEnum.REJECTED,
        }
    )
    valid_schema: ClassVar[dict] = build_valid_schema(
        valid_transition_states,
        RootModel[str],
    )
