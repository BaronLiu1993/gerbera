from dataclasses import dataclass, field

from gerbera_harness.agent.experiments.states.schema.execute.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.experiments.states.schema.execute.act import (
    ActState,
)
from gerbera_harness.agent.experiments.states.schema.execute.decide import (
    DecideState,
    ExecuteLoopDecisionEnum,
)
from gerbera_harness.agent.experiments.states.schema.execute.observe import (
    ObserveState,
)


@dataclass
class ExecuteLoop:
    state: ExecuteLoopState = field(default_factory=ObserveState)
    decision: ExecuteLoopDecisionEnum | None = None

    def valid_transition(
        self,
        new_state: ExecuteLoopStateEnum | str,
    ) -> bool:
        if self.terminated:
            return False

        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)