from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop import (
    InitialistationDecisionEnum,
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

    # Runtimes
    _initialisation_runtime: InitialisationRuntime | None = field(
        default=None,
        init=False,
        repr=False,
    )
    

    async def run_agent(self, initial_user_prompt: str) -> None:
        while True:
            current_state = self.session.state

            if current_state.state is LoopStateEnum.INITIALISATION:
                result = await self._get_initialisation_runtime().run(
                    initial_user_prompt,
                    current_state.system_prompt,
                    current_state.valid_schema,
                )
                if result is None:
                    return

                self.clarification_questions = dict(
                    result.clarifying_questions
                )

                if (
                    result.decision
                    is not InitialistationDecisionEnum.ACCEPTED
                ):
                    return

                self.current_hypothesis = result.hypothesis
                self.session.perform_transition(result.requested_next_state)
            elif current_state.state is LoopStateEnum.EXECUTION:
                if self.initialisation_process is None:
                    raise RuntimeError("InitialisationProcess is required")
                if self.current_hypothesis is None:
                    raise RuntimeError(
                        "A validated hypothesis is required for execution"
                    )

                execution_process = ExecutionProcess(
                    mcp_url=self.initialisation_process.mcp_url,
                    actions_list=(
                        self.current_hypothesis.method.execute_steps
                    ),
                )
                await execution_process.run_workflow()
                break
            elif current_state.state is LoopStateEnum.REVIEW:
                break
