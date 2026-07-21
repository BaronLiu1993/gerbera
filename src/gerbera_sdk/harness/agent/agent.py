from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execute,
    ExperimentState,
    Hypothesize,
    LoopStateEnum,
    Observe,
    Plan,
    Review,
)
from gerbera_sdk.harness.agent.model.model import Model

from gerbera_sdk.harness.memory.event import Message



STATE_REGISTRY: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.HYPOTHESIZE: Hypothesize,
    LoopStateEnum.PLAN: Plan,
    LoopStateEnum.EXECUTE: Execute,
    LoopStateEnum.OBSERVE: Observe,
    LoopStateEnum.REVIEW: Review,
    LoopStateEnum.COMPLETE: Complete,
}

class Agent:
    session: Session
    model: Model

    def run_agent(self, messages: list[Message]):
        while self.session.state != LoopStateEnum.COMPLETE:
            current_state = self.session.state
            system_prompt = STATE_REGISTRY[current_state].system_prompt
            next_state, response = Model.get_agent_client().send(messages, system_prompt)

            if current_state.valid_transition(next_state):
                self.session.state = next_state
