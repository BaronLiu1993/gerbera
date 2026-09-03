from dataclasses import dataclass

from gerbera_harness.runtime.session import (
    TaskDecompositionDecisionEnum,
    LoopStateEnum,
    Session,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import EventTypeEnum, Memory
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.runtime.evaluation_runtime import EvaluationRuntime
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.runtime.execute_producer.state_machine import StateMachine
from gerbera_harness.runtime.execute_producer.schemas import ExecuteProducerDecision
from gerbera_harness.runtime.execute_producer_runtime import ExecuteProducerRuntime
from gerbera_harness.runtime.schemas import (
    AgentResultSchema,
    AgentStatusEnum,
    ExecutionDecisionEnum,
    ExecutionResultSchema,
    EvaluationDecisionEnum,
    EvaluationResultSchema,
)
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
    previous_phase_context: str = ""
    max_task_execution_attempts: int = 5
    max_task_decomposition_retries: int = 5

    def task_execution_attempts_exhausted(self) -> bool:
        current_task = self.memory.get_current_task_state()
        return current_task.attempts >= self.max_task_execution_attempts

    def fail_current_task(self, message: str) -> ExecutionResultSchema:
        self.memory.fail_task()
        self.memory.insert_task_lifecycle_event(EventTypeEnum.TASK_FAILED)
        return ExecutionResultSchema(
            decision=ExecutionDecisionEnum.FAILED,
            message=message,
        )

    async def run_agent(self) -> AgentResultSchema:
        while True:
            current_state = self.session.state
            if current_state.state is LoopStateEnum.TASK_DECOMPOSITION:
                await self.run_task_decomposition()
            elif current_state.state is LoopStateEnum.EXECUTION:
                execution_result = await self.run_execution()
                if execution_result.decision is ExecutionDecisionEnum.FAILED:
                    return AgentResultSchema(
                        status=AgentStatusEnum.FAILED,
                        message=execution_result.message,
                    )
            elif current_state.state is LoopStateEnum.EVALUATION:
                evaluation_result = await self.run_evaluation()
                if evaluation_result.decision is EvaluationDecisionEnum.SUCCEEDED:
                    return AgentResultSchema(
                        status=AgentStatusEnum.SUCCESS,
                        message=evaluation_result.context,
                    )
                if evaluation_result.decision is EvaluationDecisionEnum.FAILED:
                    return AgentResultSchema(
                        status=AgentStatusEnum.FAILED,
                        message=evaluation_result.context,
                    )
                if evaluation_result.decision is EvaluationDecisionEnum.CONTINUE:
                    self.previous_phase_context = evaluation_result.context
                    self.session.perform_transition(
                        LoopStateEnum.TASK_DECOMPOSITION
                    )
                    continue
                raise ValueError("Unsupported Evaluation Decision")
            else:
                raise ValueError("Unsupported Main Loop State Enum")

    async def run_task_decomposition(
        self,
        source_urls: list[str] | None = None,
    ) -> None:
        result = await TaskDecompositionRuntime(
            model=self.model,
            memory=self.memory,
            tool_client=self.tool_client,
            user_prompt=self.user_prompt,
            previous_context=self.previous_phase_context,
        ).run_task_decomposition(
            source_urls=source_urls
        )  # we will pass in the source_urls eventually

        if result.decision is TaskDecompositionDecisionEnum.ACCEPTED:
            # Previous context is only for the next decomposition pass. Once a
            # new task list is accepted, clear it so later runs are not treated
            # like the same replan.
            self.previous_phase_context = ""
            self.session.perform_transition(LoopStateEnum.EXECUTION)
            return

        raise ValueError("Unsupported TaskDecomposition Decision")

    async def run_execution(self) -> ExecutionResultSchema:
        self.memory.require_task_state()
        while self.memory.has_remaining_tasks():
            self.memory.advance_to_next_task()
            self.memory.start_task()
            self.memory.insert_task_lifecycle_event(EventTypeEnum.TASK_STARTED)
            while True:
                current_task = self.memory.get_current_task_state()
                # Task attempts count failed/replan recovery cycles, not the
                # first execution pass.
                if self.task_execution_attempts_exhausted():
                    return self.fail_current_task(
                        "current task exceeded recovery attempts"
                    )

                result = await ExecuteProducerRuntime(
                    model=self.model,
                    memory=self.memory,
                    execute_consumer=self.execute_consumer,
                    state_machine=StateMachine(),
                ).produce_action_groups()

                if result.decision is ExecuteProducerDecision.REPLAN_ACTIONS:
                    self.memory.increment_current_task_attempts()
                    if self.task_execution_attempts_exhausted():
                        self.previous_phase_context = result.context
                        return self.fail_current_task(
                            "current task exceeded action replan attempts"
                        )
                    # Re-run the full execute producer workflow for the same
                    # task. A fresh producer state machine starts at OBSERVE.
                    continue

                elif result.decision is ExecuteProducerDecision.REDECOMPOSE_TASKS:
                    if (
                        self.session.current_agent_retries
                        >= self.max_task_decomposition_retries
                    ):
                        # Leave memory/session as-is for audit. At this point
                        # the agent exhausted full redecomposition attempts, so
                        # callers can inspect the current task, events, and
                        # last review context instead of seeing cleaned state.
                        return ExecutionResultSchema(
                            decision=ExecutionDecisionEnum.FAILED,
                            message="agent exceeded task redecomposition attempts",
                        )

                    self.fail_current_task("current task requested redecomposition")
                    # Clearing task state means structured audit for the old
                    # task list lives in events/context. Archive task_state here
                    # later if we need full task-list history after redecompose.
                    self.memory.clear_task_state()
                    self.session.increment_current_agent_retries()
                    self.previous_phase_context = result.context
                    self.session.perform_transition(LoopStateEnum.TASK_DECOMPOSITION)
                    return ExecutionResultSchema(
                        decision=ExecutionDecisionEnum.CONTINUE,
                        message="redecomposing tasks",
                    )

                elif result.decision is ExecuteProducerDecision.FAIL:
                    self.memory.increment_current_task_attempts()
                    if self.task_execution_attempts_exhausted():
                        return self.fail_current_task(
                            "current task failed after recovery attempts"
                        )
                    # Generic execution failure also retries the full workflow
                    # from OBSERVE while the current task remains valid.
                    continue

                elif result.decision is ExecuteProducerDecision.SUCCESS:
                    self.memory.complete_task()
                    self.memory.insert_task_lifecycle_event(
                        EventTypeEnum.TASK_COMPLETED
                    )
                    break

                else:
                    raise ValueError("Unsupported Review Decision")

        self.session.perform_transition(LoopStateEnum.EVALUATION)
        return ExecutionResultSchema(
            decision=ExecutionDecisionEnum.SUCCEEDED,
            message="execution completed",
        )

    async def run_evaluation(self) -> EvaluationResultSchema:
        return await EvaluationRuntime(
            model=self.model,
            memory=self.memory,
            tool_client=self.tool_client,
        ).run_evaluation()
