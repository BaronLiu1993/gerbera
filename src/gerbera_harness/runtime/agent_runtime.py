from dataclasses import dataclass, field
from functools import cached_property

from gerbera_harness.runtime.session import (
    ExecuteDecisionEnum,
    InitialisationDecisionEnum,
    LoopStateEnum,
    ReviewDecisionEnum,
    Session,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.runtime.context import (
    ReviewContextBuilder,
)
from gerbera_harness.runtime.execution import ExecutionRuntime
from gerbera_harness.runtime.initialisation_runtime import (
    InitialisationRuntime,
)
from gerbera_harness.runtime.review_runtime import ReviewRuntime


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory
    mcp_url: str
    local_tool_registry: LocalToolRegistry
    feedback: list[str] = field(default_factory=list)
    context_window_size: int = 20

    @cached_property
    def initialisation_runtime(self) -> InitialisationRuntime:
        self._initialisation_runtime = InitialisationRuntime(
            model=self.model,
            memory=self.memory,
            tool_client=ToolClient(
                mcp_url=self.mcp_url,
                local_tool_registry=self.local_tool_registry,
            ),
        )
        return self._initialisation_runtime

    @cached_property
    def execution_runtime(self) -> ExecutionRuntime:
        return ExecutionRuntime(
            model=self.model,
            memory=self.memory,
            mcp_url=self.mcp_url,
            local_tool_registry=self.local_tool_registry,
        )

    @cached_property
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
                    sources=[],
                    feedback=initial_user_prompt,
                )

                print("initialisation result", result)

                if result.decision is InitialisationDecisionEnum.ACCEPTED:
                    self.memory.initialisation_intent = result.intent
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
