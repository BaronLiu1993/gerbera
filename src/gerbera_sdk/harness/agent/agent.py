from dataclasses import dataclass
import json

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

from gerbera_sdk.harness.memory.event import (
    Event,
    EventTypeEnum,
    SourceTypeEnum,
)
from gerbera_sdk.harness.memory.memory import Memory


STATE_REGISTRY: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.HYPOTHESIZE: Hypothesize,
    LoopStateEnum.PLAN: Plan,
    LoopStateEnum.EXECUTE: Execute,
    LoopStateEnum.OBSERVE: Observe,
    LoopStateEnum.REVIEW: Review,
    LoopStateEnum.COMPLETE: Complete,
}


@dataclass
class Agent:
    session: Session
    model: Model
    memory: Memory

    def run_agent(self, messages: list[dict]) -> None:
        client = self.model.get_agent_client()

        while self.session.state.state != LoopStateEnum.COMPLETE:
            current_state = self.session.state
            raw_response = client.send(messages, current_state.prompt, current_state.valid_schema)
            output = json.loads(raw_response)
            next_state = LoopStateEnum(output["next_state"])

            if not current_state.valid_transition(next_state):
                raise ValueError(
                    f"Invalid transition: {current_state.state.value} "
                    f"to {next_state.value}"
                )

            event = Event(
                event_type=EventTypeEnum.STATE_RESPONSE,
                source_type=SourceTypeEnum.MODEL,
                payload={
                    "next_state": next_state.value,
                    "response": output["response"],
                },
                session_id=self.session.id,
            )
            self.memory.append_event(current_state.state.value, event)
            self.session.state = STATE_REGISTRY[next_state]()
