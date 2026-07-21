from dataclasses import dataclass, field
import json

from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execution,
    ExperimentState,
    Failed,
    Initialisation,
    LoopStateEnum,
    Observation,
    Plan,
    Review,
)
from gerbera_sdk.harness.agent.model.model import AgentClient, Model

from gerbera_sdk.harness.memory.event import (
    Event,
    EventTypeEnum,
    SourceTypeEnum,
)
from gerbera_sdk.harness.memory.memory import Memory


STATE_REGISTRY: dict[LoopStateEnum, type[ExperimentState]] = {
    LoopStateEnum.INITIALISATION: Initialisation,
    LoopStateEnum.PLAN: Plan,
    LoopStateEnum.EXECUTION: Execution,
    LoopStateEnum.OBSERVATION: Observation,
    LoopStateEnum.REVIEW: Review,
    LoopStateEnum.COMPLETE: Complete,
    LoopStateEnum.FAILED: Failed,
}

TERMINAL_STATES = frozenset({LoopStateEnum.COMPLETE, LoopStateEnum.FAILED})


@dataclass
class Agent:
    session: Session
    model: Model
    memory: Memory
    messages: list[dict[str, str]] = field(default_factory=list)
    context_window_size: int = 20

    def run_agent(self) -> None:
        if self.context_window_size < 1:
            raise ValueError("Context window size must be positive")

        client = self.model.get_agent_client()

        while self.session.state.state not in TERMINAL_STATES:
            current_state = self.session.state
            next_state, response = self._request_transition(
                client,
                current_state,
            )
            self._record_response(current_state, next_state, response)
            self.session.state = STATE_REGISTRY[next_state]()

    def _request_transition(
        self,
        client: AgentClient,
        current_state: ExperimentState,
    ) -> tuple[LoopStateEnum, str]:
        raw_response = client.send(
            self.messages[-self.context_window_size :],
            current_state.prompt,
            current_state.valid_schema,
        )
        output = json.loads(raw_response)
        next_state = LoopStateEnum(output["next_state"])

        if not current_state.valid_transition(next_state):
            raise ValueError(
                f"Invalid transition: {current_state.state.value} "
                f"to {next_state.value}"
            )
        
        self.session.state = next_state
        return next_state, output["response"]

    def _record_response(
        self,
        current_state: ExperimentState,
        next_state: LoopStateEnum,
        response: str,
    ) -> None:
        event = Event(
            event_type=EventTypeEnum.STATE_RESPONSE,
            source_type=SourceTypeEnum.MODEL,
            payload={
                "next_state": next_state.value,
                "response": response,
            },
            session_id=self.session.id,
        )
        self.memory.append_event(current_state.state.value, event)
        self.messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "state": current_state.state.value,
                        **event.payload,
                    }
                ),
            }
        )
        self.messages[:] = self.messages[-self.context_window_size:]
