from dataclasses import dataclass

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.runtime.context import (
    ObservationContextBuilder,
    PlanningContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.runtime.execute_producer.observe_runtime import (
    ObservationRuntime,
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
    ObservationDecision,
    PlanningDecision,
    ReviewDecision,
    ReviewResult,
)
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema
from gerbera_harness.tools.client import ToolClient


@dataclass
class ExecuteProducerRuntime:
    model: Model
    tool_client: ToolClient
    memory: Memory
    context: str
    execute_consumer: ExecuteConsumerRuntime
    state_machine: StateMachine
    max_turns: int = 3

    async def submit_action_groups(
        self,
        action_groups: list[list[ActionExecuteSchema]],
    ) -> None:
        await self.execute_consumer.execute_actions(action_groups=action_groups)

    async def produce_action_groups(self) -> ReviewResult:
        for _ in range(self.max_turns):
            if self.state_machine.current_state is ExecuteLoopStateEnum.OBSERVE:
                observation = await ObservationRuntime(
                    model=self.model,
                    memory=self.memory,
                    # Tool calls go straight through the consumer for now.
                    # Reintroduce a producer wrapper here only if the producer
                    # needs to enforce permissions, retries, or routing.
                    call_tool=self.execute_consumer.call_tool,
                    context_builder=ObservationContextBuilder(
                        memory=self.memory,
                    ),
                    prev_state_context=self.context,
                ).run_observation()

                if observation.result is ObservationDecision.FAIL:
                    return ReviewResult(
                        decision=ReviewDecision.FAIL,
                        context=observation.context,
                    )

                await self.submit_action_groups(observation.actions)
                self.context = observation.context
                self.state_machine.perform_transition(ExecuteLoopStateEnum.PLAN)
            elif self.state_machine.current_state is ExecuteLoopStateEnum.PLAN:
                planning = await PlanningRuntime(
                    model=self.model,
                    memory=self.memory,
                    prev_state_context=self.context,
                    context_builder=PlanningContextBuilder(
                        memory=self.memory,
                    ),
                ).run_planning()

                if planning.result is PlanningDecision.FAIL:
                    return ReviewResult(
                        decision=ReviewDecision.FAIL,
                        context=planning.context,
                    )

                action_groups = planning.actions
                await self.submit_action_groups(action_groups)

                self.context = planning.context
                self.state_machine.perform_transition(ExecuteLoopStateEnum.REVIEW)
            elif self.state_machine.current_state is ExecuteLoopStateEnum.REVIEW:
                review = await ReviewRuntime(
                    model=self.model,
                    memory=self.memory,
                    # Tool calls go straight through the consumer for now.
                    # Reintroduce a producer wrapper here only if the producer
                    # needs to enforce permissions, retries, or routing.
                    call_tool=self.execute_consumer.call_tool,
                    context_builder=ReviewContextBuilder(memory=self.memory),
                    prev_state_context=self.context,
                ).run_review()
                self.context = review.context
                if review.decision is ReviewDecision.REPLAN_ACTIONS:
                    self.state_machine.perform_transition(
                        ExecuteLoopStateEnum.OBSERVE
                    )
                    continue

                return review
            else:
                raise ValueError("Unsupported State")

        return ReviewResult(
            decision=ReviewDecision.REDECOMPOSE_TASKS,
            context=(
                "Exceeded execute producer max turns while trying to complete "
                "the current task."
            ),
        )
