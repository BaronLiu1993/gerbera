from dataclasses import dataclass

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.runtime.context import (
    ObservationContextBuilder,
    PlanningContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.runtime.execute_consumer import ExecuteConsumer
from gerbera_harness.runtime.execute_producer.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.runtime.execute_producer.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.runtime.execute_producer.review_runtime import ReviewRuntime
from gerbera_harness.runtime.execute_producer.session import (
    ExecuteLoopStateEnum,
    LoopDecision,
    StateMachine,
)
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema
from gerbera_harness.tools.client import ToolClient


@dataclass
class ExecuteProducer:
    model: Model
    tool_client: ToolClient
    memory: Memory
    context: str
    execute_consumer: ExecuteConsumer
    state_machine: StateMachine
    max_turns: int = 3

    async def submit_action_groups(
        self,
        action_groups: list[list[ActionExecuteSchema]],
    ) -> None:
        await self.execute_consumer.execute_actions(action_groups=action_groups)

    async def produce_action_groups(self) -> None:
        while True:
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

                if observation.result is LoopDecision.FAIL:
                    break

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

                if planning.result is LoopDecision.FAIL:
                    break

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
                if review.result is LoopDecision.FAIL:
                    break

                await self.submit_action_groups(review.actions)
                self.context = review.context
                break
                # we are only coding the happy path right now, so review will basically be another observe with a different system prompt
                # and extra review
                # if review.result is LoopDecision.FAIL:
                #     self.state_machine.perform_transition(ExecuteLoopStateEnum.OBSERVE)
            else:
                raise ValueError("Unsupported State")
