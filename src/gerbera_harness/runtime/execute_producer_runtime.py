from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.runtime.context import (
    ObservationContextBuilder,
    ObservationReviewContextBuilder,
    PlanningContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.runtime.execute_producer.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.runtime.execute_producer.schemas.observe import (
    ObservationIterationContext,
    ObservationIterationRole,
)
from gerbera_harness.runtime.execute_producer.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.runtime.execute_producer.review_runtime import ReviewRuntime
from gerbera_harness.runtime.execute_producer.state_machine import (
    ExecuteLoopStateEnum,
    StateMachine,
)
from gerbera_harness.runtime.execute_producer.schemas import (
    ExecuteProducerDecision,
    ExecuteProducerResult,
    ObservationDecision,
    PlanningIterationContext,
    PlanningIterationRole,
    PlanningReviewDecision,
)
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


@dataclass
class ExecuteProducerRuntime:
    model: Model
    memory: Memory
    task_goal: str
    execute_consumer: ExecuteConsumerRuntime
    state_machine: StateMachine
    observation_iteration_context: list[ObservationIterationContext] = field(
        default_factory=list
    )
    planning_iteration_context: list[PlanningIterationContext] = field(
        default_factory=list
    )
    max_retries: int = 5
    prev_state_context: str = "" # passes in the task description

    async def submit_action_groups(
        self,
        action_groups: list[list[ActionExecuteSchema]],
        *,
        read_only_required: bool = False,
    ) -> list[dict[str, Any]]:
        return await self.execute_consumer.execute_actions(
            action_groups=action_groups,
            read_only_required=read_only_required,
        )

    async def produce_action_groups(self) -> ExecuteProducerResult:
        available_tools = [
            tool.model_dump()
            for tool in await self.execute_consumer.tool_client.list_tools()
        ]
        read_only_tools = [
            tool
            for tool in available_tools
            if tool.get("read_only") is True
        ]

        while True:
            if self.state_machine.current_state is ExecuteLoopStateEnum.OBSERVE:
                for iteration_index in range(self.max_retries):
                    observation_runtime = ObservationRuntime(
                        model=self.model,
                        memory=self.memory,
                        call_tool=self.execute_consumer.call_read_only_tool,
                        context_builder=ObservationContextBuilder(
                            memory=self.memory,
                            available_tools=read_only_tools,
                        ),
                        review_context_builder=ObservationReviewContextBuilder(
                            memory=self.memory,
                            available_tools=read_only_tools,
                        ),
                        prev_state_context=self.prev_state_context,
                        prev_iteration_context=self.observation_iteration_context,
                        current_iteration=iteration_index + 1,
                        max_iterations=self.max_retries,
                    )
                    observation = await observation_runtime.run_observation()

                    if observation.actions:
                        tool_results = await self.submit_action_groups(
                            observation.actions,
                            read_only_required=True,
                        )
                        for tool_result in tool_results:
                            observation_runtime.append_iteration_context(
                                role=ObservationIterationRole.TOOL,
                                content=tool_result,
                            )

                    observation_review = (
                        await observation_runtime.run_observation_review(
                            observation
                        )
                    )
                    if observation_review.decision is ObservationDecision.FAIL:
                        return ExecuteProducerResult(
                            decision=ExecuteProducerDecision.FAIL,
                            context=observation_review.context,
                        )
                    elif (
                        observation_review.decision
                        is ObservationDecision.SUCCEEDED
                    ):
                        self.prev_state_context = observation_review.context
                        self.state_machine.perform_transition(
                            ExecuteLoopStateEnum.PLAN
                        )
                        break
                    elif observation_review.decision is ObservationDecision.RETRY:
                        continue
                    else:
                        raise ValueError(
                            "Unsupported observation review decision"
                        )
                else:
                    return ExecuteProducerResult(
                        decision=ExecuteProducerDecision.FAIL,
                        context="observation exceeded max retries",
                    )
            elif self.state_machine.current_state is ExecuteLoopStateEnum.PLAN:
                for iteration_index in range(self.max_retries):
                    planning_runtime = PlanningRuntime(
                        model=self.model,
                        memory=self.memory,
                        prev_state_context=self.prev_state_context,
                        context_builder=PlanningContextBuilder(
                            memory=self.memory,
                            available_tools=available_tools,
                        ),
                        prev_iteration_context=self.planning_iteration_context,
                        current_iteration=iteration_index + 1,
                        max_iterations=self.max_retries,
                    )
                    planning = await planning_runtime.run_planning()
                    planning_review = await planning_runtime.run_planning_review(
                        planning
                    )

                    if (
                        planning_review.decision
                        is PlanningReviewDecision.FAIL
                    ):
                        return ExecuteProducerResult(
                            decision=ExecuteProducerDecision.FAIL,
                            context=planning_review.context,
                        )
                    elif (
                        planning_review.decision
                        is PlanningReviewDecision.APPROVED
                    ):
                        if planning.actions:
                            tool_results = await self.submit_action_groups(
                                planning.actions
                            )
                            for tool_result in tool_results:
                                planning_runtime.append_iteration_context(
                                    role=PlanningIterationRole.TOOL,
                                    content=tool_result,
                                )

                        self.prev_state_context = planning_review.context
                        self.state_machine.perform_transition(
                            ExecuteLoopStateEnum.REVIEW
                        )
                        break
                    elif (
                        planning_review.decision
                        is PlanningReviewDecision.REVISE
                    ):
                        self.prev_state_context = planning_review.context
                        continue
                    else:
                        raise ValueError("Unsupported planning review decision")
                else:
                    return ExecuteProducerResult(
                        decision=ExecuteProducerDecision.FAIL,
                        context="planning exceeded max retries",
                    )
            elif self.state_machine.current_state is ExecuteLoopStateEnum.REVIEW:
                review = await ReviewRuntime(
                    model=self.model,
                    memory=self.memory,
                    call_tool=self.execute_consumer.call_read_only_tool,
                    context_builder=ReviewContextBuilder(
                        memory=self.memory,
                        available_tools=read_only_tools,
                    ),
                    prev_state_context=self.prev_state_context,
                ).run_review()
                return review
            else:
                raise ValueError("Unsupported State")
