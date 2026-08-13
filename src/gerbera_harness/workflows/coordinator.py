from dataclasses import dataclass, field

from gerbera_harness.domain.session import (
    InitialisationDecisionEnum,
    ExecuteDecisionEnum,
    LoopStateEnum,
    ReviewDecisionEnum,
    Session,
)
from gerbera_harness.workflows.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.infrastructure.llm import Model
from gerbera_harness.workflows.context import (
    InitialisationContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.workflows.initialisation import (
    InitialisationRuntime,
)
from gerbera_harness.workflows.execution import (
    ExecutionRuntime,
)
from gerbera_harness.workflows.review import (
    ReviewRuntime,
)
from gerbera_harness.memory import Memory
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory
    mcp_url: str
    local_tool_registry: LocalToolRegistry
    feedback: list[str] = field(default_factory=list)
    context_window_size: int = 20

    @property
    def initialisation_runtime(self) -> InitialisationRuntime:
        self._initialisation_runtime = InitialisationRuntime(
            model=self.model,
            memory=self.memory,
            context_builder=InitialisationContextBuilder(
                memory=self.memory,
                context_window_size=self.context_window_size,
            ),
            process=InitialisationProcess(
                mcp_url=self.mcp_url,
                local_tools=tuple(self.local_tool_registry.list_tools()),
            ),
        )
        return self._initialisation_runtime

    @property
    def execution_runtime(self) -> ExecutionRuntime:
        return ExecutionRuntime(
            model=self.model,
            memory=self.memory,
            mcp_url=self.mcp_url,
            local_tool_registry=self.local_tool_registry,
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
            print(
                "run_agent state",
                {
                    "session_id": self.session.session_id,
                    "memory_session_id": self.memory.session_id,
                    "state": current_state.state.value,
                },
            )
            if current_state.state is LoopStateEnum.INITIALISATION:
                result = await self.initialisation_runtime.run_initial(
                    initial_user_prompt,
                    self.feedback,
                )

                print("initialisation result", result)

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
                print("execution result", result)
                if result.decision is ExecuteDecisionEnum.ACCEPTED:
                    self.session.perform_transition(result.requested_next_state)
                elif result.decision is ExecuteDecisionEnum.REJECTED:
                    break
                else:
                    raise ValueError("Unsupported Decision")
            elif current_state.state is LoopStateEnum.REVIEW:
                result = await self.review_runtime.run_review()
                print("review result", result)
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
