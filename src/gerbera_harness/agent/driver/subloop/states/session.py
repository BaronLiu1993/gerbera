from dataclasses import dataclass, field

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopState,
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.act import (
    ActState,
)
from gerbera_harness.agent.driver.subloop.schema.decide import (
    ExecuteLoopDecisionEnum,
)
from gerbera_harness.agent.driver.subloop.states.decide import (
    DecideState,
)
from gerbera_harness.agent.driver.subloop.states.observe import (
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
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)
