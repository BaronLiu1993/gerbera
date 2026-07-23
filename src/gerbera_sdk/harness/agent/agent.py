from dataclasses import dataclass, field
import json

from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states.processes.initialisation_process import (
    InitialisationProcess,
)
from gerbera_sdk.harness.agent.experiments.states import (
    ExperimentState,
    LoopStateEnum,
    DecisionEnum
)
from gerbera_sdk.harness.agent.model.model import Model

from gerbera_sdk.harness.memory.event import (
    Event,
    EventTypeEnum,
    SourceTypeEnum,
)

from gerbera_sdk.harness.memory.memory import Memory


@dataclass
class Agent:
    session: Session
    model: Model
    memory: Memory
    initialisation_process: InitialisationProcess | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    context_window_size: int = 20

    async def prepare_initialisation_context(self, user_prompt: str) -> str:
        if self.session.state.state is not LoopStateEnum.INITIALISATION:
            raise RuntimeError(
                "Initialisation context can only be prepared during initialisation"
            )

        context = await self.initialisation_process.run(user_prompt)
        self.messages.append({"role": "user", "content": context})
        return context

    async def run_agent(self, initial_user_prompt: str) -> None:
        client = self.model.get_agent_client()
        while self.session.state.state != LoopStateEnum.COMPLETE.value:
            system_prompt = self.session.state.system_prompt
            valid_schema = self.session.state.valid_schema
            if self.session.state.state == LoopStateEnum.INITIALISATION.value:
                await self.prepare_initialisation_context(initial_user_prompt)
                raw_response = client.send(self.messages, system_prompt, valid_schema)
                message = json.loads(raw_response)

                decision = message["decision"]
                next_state = message["next_state"]
                #print(json.dumps(message, indent=4))

                if decision == DecisionEnum.ACCEPTED.value:
                    #print(decision)
                    #print(next_state)
                    break
                else:
                    print("breaking")
                    break
                    
                
        



    # def _record_response(
    #     self,
    #     current_state: ExperimentState,
    #     next_state: LoopStateEnum,
    #     response: Any,
    # ) -> None:
    #     event = Event(
    #         event_type=EventTypeEnum.STATE_RESPONSE,
    #         source_type=SourceTypeEnum.MODEL,
    #         payload={
    #             "next_state": next_state.value,
    #             "response": response,
    #         },
    #         session_id=self.session.id,
    #     )
    #     self.memory.append_event(current_state.state.value, event)
    #     self.messages.append(
    #         {
    #             "role": "assistant",
    #             "content": json.dumps(
    #                 {
    #                     "state": current_state.state.value,
    #                     **event.payload,
    #                 }
    #             ),
    #         }
    #     )
