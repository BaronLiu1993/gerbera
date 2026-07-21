from gerbera_sdk.harness.agent.model.model import Model
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states.base import LoopStateEnum

STATE_REGISTRY = {

}

class Agent:
    session: Session
    model: Model

    def run_agent(self):
        current_state = self.session.state

        while current_state != LoopStateEnum.COMPLETE:
             STATE_REGISTRY[current_state]
