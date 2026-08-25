from dataclasses import dataclass

from gerbera_harness.runtime.session import (
    TaskDecompositionDecisionEnum,
    LoopStateEnum,
    Session,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.runtime.evaluation_runtime import EvaluationRuntime
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.runtime.execute_producer.state_machine import StateMachine
from gerbera_harness.runtime.execute_producer.schemas import ReviewDecision
from gerbera_harness.runtime.execute_producer_runtime import ExecuteProducerRuntime
from gerbera_harness.runtime.task_decomposition_runtime import (
    TaskDecompositionRuntime,
)


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory
    tool_client: ToolClient
    execute_consumer: ExecuteConsumerRuntime
    user_prompt: str
    previous_context: str = ""
    max_task_retries: int = 5
    max_agent_retries: int = 5

    async def run_agent(self) -> None:
        while True:
            current_state = self.session.state
            if current_state.state is LoopStateEnum.TASK_DECOMPOSITION:
                await self.run_task_decomposition()
            elif current_state.state is LoopStateEnum.EXECUTION:
                await self.run_execution()
            elif current_state.state is LoopStateEnum.EVALUATION:
                await self.run_evaluation()
                break
            else:
                raise ValueError("Unsupported Main Loop State Enum")

    async def run_task_decomposition(self, source_urls: list[str] = []) -> None:
        result = await TaskDecompositionRuntime(
            model=self.model,
            memory=self.memory,
            tool_client=self.tool_client,
            user_prompt=self.user_prompt,
            previous_context=self.previous_context,
        ).run_task_decomposition(
            source_urls=source_urls
        )  # we will pass in the source_urls eventually

        if result.decision is TaskDecompositionDecisionEnum.ACCEPTED:
            # Previous context is only for the next decomposition pass. Once a
            # new task list is accepted, clear it so later runs are not treated
            # like the same replan.
            self.previous_context = ""
            self.session.perform_transition(LoopStateEnum.EXECUTION)
            return

        raise ValueError("Unsupported TaskDecomposition Decision")

    async def run_execution(self) -> None:
        self.memory.require_task_state()
        while self.memory.has_remaining_tasks():
            self.memory.advance_to_next_task()
            self.memory.start_task()
            while True:
                current_task = self.memory.get_current_task_state()
                if current_task.attempts >= self.max_task_retries:
                    self.memory.fail_task()
                    return

                result = await ExecuteProducerRuntime(
                    model=self.model,
                    tool_client=self.tool_client,
                    memory=self.memory,
                    context=current_task.task_goal,
                    execute_consumer=self.execute_consumer,
                    state_machine=StateMachine(),
                ).produce_action_groups()

                if result.decision is ReviewDecision.REPLAN_ACTIONS:
                    self.memory.increment_current_task_attempts()
                    current_task = self.memory.get_current_task_state()
                    if current_task.attempts >= self.max_task_retries:
                        self.memory.fail_task()
                        self.previous_context = result.context
                        self.session.perform_transition(
                            LoopStateEnum.TASK_DECOMPOSITION
                        )
                        return
                    continue

                elif result.decision is ReviewDecision.REDECOMPOSE_TASKS:
                    if self.session.current_agent_retries >= self.max_agent_retries:
                        # Leave memory/session as-is for audit. At this point
                        # the agent exhausted full redecomposition attempts, so
                        # callers can inspect the current task, events, and
                        # last review context instead of seeing cleaned state.
                        return

                    self.memory.fail_task()
                    self.memory.clear_task_state()
                    self.session.increment_current_agent_retries()
                    self.previous_context = result.context
                    self.session.perform_transition(LoopStateEnum.TASK_DECOMPOSITION)
                    return

                elif result.decision is ReviewDecision.FAIL:
                    self.memory.increment_current_task_attempts()
                    current_task = self.memory.get_current_task_state()
                    if current_task.attempts >= self.max_task_retries:
                        self.memory.fail_task()
                        return
                    continue

                elif result.decision is ReviewDecision.SUCCESS:
                    self.memory.complete_task()
                    break

                else:
                    raise ValueError("Unsupported Review Decision")

        self.session.perform_transition(LoopStateEnum.EVALUATION)

    async def run_evaluation(self) -> None:
        await EvaluationRuntime(memory=self.memory).run_evaluation()
