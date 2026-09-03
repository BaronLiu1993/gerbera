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
    PlanningDecision,
)
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


@dataclass
class ExecuteProducerRuntime:
    model: Model
    memory: Memory
    context: str
    execute_consumer: ExecuteConsumerRuntime
    state_machine: StateMachine
    observation_iteration_context: list[ObservationIterationContext] = field(
        default_factory=list
    )
    max_retries: int = 5

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
                for _ in range(self.max_retries):
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
                        prev_iteration_context=self.observation_iteration_context,
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
                        self.context = observation_review.context
                        self.state_machine.perform_transition(
                            ExecuteLoopStateEnum.PLAN
                        )
                        break
                    elif observation_review.decision is ObservationDecision.RETRY:
                        self.context = observation_review.context
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
                for _ in range(self.max_retries):
                    planning = await PlanningRuntime(
                        model=self.model,
                        memory=self.memory,
                        prev_state_context=self.context,
                        context_builder=PlanningContextBuilder(
                            memory=self.memory,
                            available_tools=available_tools,
                        ),
                    ).run_planning()

                    if planning.decision is PlanningDecision.FAIL:
                        return ExecuteProducerResult(
                            decision=ExecuteProducerDecision.FAIL,
                            context=planning.context,
                        )

                    if planning.decision is PlanningDecision.SUCCEEDED:
                        action_groups = planning.actions
                        await self.submit_action_groups(action_groups)

                    self.context = planning.context
                    self.state_machine.perform_transition(ExecuteLoopStateEnum.REVIEW)
            elif self.state_machine.current_state is ExecuteLoopStateEnum.REVIEW:
                review = await ReviewRuntime(
                    model=self.model,
                    memory=self.memory,
                    call_tool=self.execute_consumer.call_read_only_tool,
                    context_builder=ReviewContextBuilder(
                        memory=self.memory,
                        available_tools=read_only_tools,
                    ),
                    prev_state_context=self.context,
                ).run_review()
                self.context = review.context
                return review
            else:
                raise ValueError("Unsupported State")
