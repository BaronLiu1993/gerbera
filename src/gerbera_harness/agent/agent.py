from dataclasses import dataclass, field
import json

from pydantic import ValidationError

from gerbera_harness.agent.experiments.session import Session
from gerbera_harness.agent.experiments.states.processes.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.agent.experiments.states.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.experiments.states.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.experiments.states import (
    ExperimentState,
    LoopStateEnum,
    DecisionEnum,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.memory.memory import Memory


@dataclass
class Agent:
    session: Session
    model: Model
    memory: Memory | None = None
    initialisation_process: InitialisationProcess | None = None
    max_initialisation_attempts: int = 3

    # Messages
    messages: list[dict[str, str]] = field(default_factory=list)
    context_window_size: int = 20

    # Hypothesis
    current_hypothesis: HypothesisSchema | None = None

    async def prepare_initialisation_context(self, user_prompt: str) -> str:
        if self.session.state.state is not LoopStateEnum.INITIALISATION:
            raise RuntimeError(
                "Initialisation context can only be prepared during initialisation"
            )
        if self.initialisation_process is None:
            raise RuntimeError("InitialisationProcess is required")
        
        # We Will Get More Context From Past Failures
        context = await self.initialisation_process.run(user_prompt)
        self.messages.append({"role": "user", "content": context})
        return context

    async def run_agent(self, initial_user_prompt: str) -> None:
        client = self.model.get_agent_client()
        initialisation_attempts = 0
        initialisation_context_prepared = False

        while self.session.state.state is not LoopStateEnum.COMPLETE:
            current_state = self.session.state

            if current_state.state is LoopStateEnum.INITIALISATION:
                print(current_state)
                if not initialisation_context_prepared:
                    await self.prepare_initialisation_context(
                        initial_user_prompt
                    )
                    initialisation_context_prepared = True

                initialisation_attempts += 1
                raw_response = client.send(
                    self.messages,
                    current_state.system_prompt,
                    current_state.valid_schema,
                )

                message = json.loads(raw_response)
                next_state = LoopStateEnum(message["next_state"])
                decision = DecisionEnum(message["decision"])

                print(message)

                if decision is DecisionEnum.REJECTED:
                    return

                try:
                    self.current_hypothesis = (
                        HypothesisSchema.model_validate(message["response"])
                    )
                except ValidationError as exc:
                    if (
                        initialisation_attempts
                        >= self.max_initialisation_attempts
                    ):
                        raise RuntimeError(
                            "Initialisation produced an invalid experiment "
                            f"plan after {initialisation_attempts} attempts"
                        ) from exc

                    self.messages.extend(
                        [
                            {
                                "role": "assistant",
                                "content": raw_response,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "The proposed experiment plan failed "
                                    "schema validation. Return the complete "
                                    "corrected plan, preserving the objective "
                                    "and satisfying every validation error. "
                                    "Validation errors:\n"
                                    f"{exc.json(
                                        include_url=False,
                                        include_input=False,
                                        indent=2,
                                    )}"
                                ),
                            },
                        ]
                    )
                    continue

                self.session.perform_transition(next_state)
            elif current_state.state is LoopStateEnum.EXECUTION:

                print(current_state)
                execution_process = ExecutionProcess(
                    mcp_url=self.initialisation_process.mcp_url,
                    actions_list=(
                        self.current_hypothesis.method.execute_steps
                    ),
                )

                await execution_process.run_workflow()
                break
            elif current_state.state is LoopStateEnum.REVIEW.value:
                    

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
