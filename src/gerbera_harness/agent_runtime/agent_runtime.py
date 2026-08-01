from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop import (
    InitialisationDecisionEnum,
    LoopStateEnum,
    Session,
)
from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.processes.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)

from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.main_loop.initialisation_runtime import (
    InitialisationRuntime,
)
from gerbera_harness.agent_runtime.main_loop.utils import append_message
from gerbera_harness.memory.memory import Memory


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory | None = None
    messages: list[dict[str, object]] = field(default_factory=list)
    context_window_size: int = 20
    current_hypothesis: HypothesisSchema | None = None

    @property
    def initialisation_runtime(self) -> InitialisationRuntime:
        self._initialisation_runtime = InitialisationRuntime(
            model=self.model,
            messages=self.messages,
        )
        return self._initialisation_runtime

    async def run_agent(self, initial_user_prompt: str) -> None:
        while True:
            current_state = self.session.state
            if current_state.state is LoopStateEnum.INITIALISATION:
                result = await self.initialisation_runtime.run_initial(
                    initial_user_prompt,
                    current_state.system_prompt,
                )

                if result.decision is InitialisationDecisionEnum.ACCEPTED:
                    self.current_hypothesis = result.hypothesis
                    self.session.state.state = self.session.perform_transition(result.requested_next_state)
                elif result.decision is InitialisationDecisionEnum.CLARIFY:
                    break
                elif result.decision is InitialisationDecisionEnum.REJECTED:
                    return result.rejection_reasons
                else:
                    raise ValueError("Unsupported Decision")
            elif current_state.state is LoopStateEnum.EXECUTION:
                pass

            #     if self.current_hypothesis is None:
            #         raise RuntimeError(
            #             "A validated hypothesis is required for execution"
            #         )

            #     execution_process = ExecutionProcess(
            #         mcp_url=self.initialisation_process.mcp_url,
            #         actions_list=(
            #             self.current_hypothesis.method.execute_steps
            #         ),
            #     )
            #     await execution_process.run_workflow()
            #     break
            # elif current_state.state is LoopStateEnum.REVIEW:
            #     break
