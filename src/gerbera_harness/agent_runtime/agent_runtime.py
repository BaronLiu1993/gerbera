from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop import (
    InitialisationDecisionEnum,
    ExecuteDecisionEnum,
    LoopStateEnum,
    ReviewDecisionEnum,
    Session,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)
from gerbera_harness.agent.driver.main_loop.processes.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.context_builder import (
    InitialisationContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.agent_runtime.main_loop.initialisation_runtime import (
    InitialisationRuntime,
)
from gerbera_harness.agent_runtime.main_loop.execution_runtime import (
    ExecutionRuntime,
)
from gerbera_harness.agent_runtime.main_loop.review_runtime import (
    ReviewRuntime,
)
from gerbera_harness.memory import Memory


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory
    mcp_url: str
    feedback: list[str]
    context_window_size: int = 20
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    @property
    def initialisation_runtime(self) -> InitialisationRuntime:
        self._initialisation_runtime = InitialisationRuntime(
            model=self.model,
            memory=self.memory,     
            context_builder=InitialisationContextBuilder(
                memory=self.memory,
                context_window_size=self.context_window_size,
            ),
            process=InitialisationProcess(mcp_url=self.mcp_url),
        )
        return self._initialisation_runtime

    @property
    def execution_runtime(self) -> ExecutionRuntime:
        return ExecutionRuntime(
            model=self.model,
            memory=self.memory,
            mcp_url=self.mcp_url,
        )

    @property
    def review_runtime(self) -> ReviewRuntime:
        return ReviewRuntime(
            model=self.model,
            memory=self.memory,
            context_builder=ReviewContextBuilder(
                memory=self.memory,
                context_window_size=self.context_window_size,
            ),
        )

    async def run_agent(self, initial_user_prompt: str) -> None:
        while True:
            current_state = self.session.state
            if current_state.state is LoopStateEnum.INITIALISATION:
                result = await self.initialisation_runtime.run_initial(
                    initial_user_prompt,
                    self.feedback,
                )

                if result.decision is InitialisationDecisionEnum.ACCEPTED:
                    if result.hypothesis is None:
                        raise RuntimeError(
                            "Accepted initialisation requires a hypothesis"
                        )
                    initialisation_memory = self.memory
                    self.memory = Memory(
                        goal=initialisation_memory.goal,
                        session_id=initialisation_memory.session_id,
                        messages=list(initialisation_memory.messages),
                        current_hypothesis=result.hypothesis,
                        event_ledger=list(
                            initialisation_memory.event_ledger
                        ),
                        world_state_ledger=list(
                            initialisation_memory.world_state_ledger
                        ),
                    )
                    self.memory.initialize_tasks(result.hypothesis)
                    self.session.perform_transition(result.requested_next_state)
                elif result.decision is InitialisationDecisionEnum.CLARIFY:
                    break
                elif result.decision is InitialisationDecisionEnum.REJECTED:
                    return result.rejection_reasons
                else:
                    raise ValueError("Unsupported Decision")
            elif current_state.state is LoopStateEnum.EXECUTION:
                result = await self.execution_runtime.run_execution()

                if result.decision is ExecuteDecisionEnum.ACCEPTED:
                    self.errors.extend(result.errors)
                    self.session.perform_transition(result.requested_next_state)
                elif result.decision is ExecuteDecisionEnum.REJECTED:
                    self.session.perform_transition(result.requested_next_state)
                else:
                    raise ValueError("Unsupported Decision")
            elif current_state.state is LoopStateEnum.REVIEW:
                result = await self.review_runtime.run_review()

                if result.decision is ReviewDecisionEnum.REPLAN:
                    self.feedback = result.feedback
                    # Replanning is intentionally paused while the first
                    # single-pass workflow is stabilized.
                    # self.session.perform_transition(result.requested_next_state)
                    break
                elif result.decision is ReviewDecisionEnum.ACCEPTED:
                    break
                elif result.decision is ReviewDecisionEnum.REJECTED:
                    break
                else:
                    raise ValueError("Unsupported Decision")
            else:
                raise ValueError("Unsupported Main Loop State Enum")
