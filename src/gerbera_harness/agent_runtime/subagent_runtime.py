from dataclasses import dataclass
from typing import field

from gerbera_harness.agent.driver.subloop.schema.act import (
    ToolCallStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningExecuteActionSchema,
    PlanningStatusEnum,
)
from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.session import Session
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.sub_loop.act_runtime import ActRuntime
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.agent_runtime.sub_loop.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.world_state_schema import (
    WorldStateSchema
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.event_schema import (
    EventSchema
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    TaskSchema
)


from gerbera_harness.memory.memory import Memory


@dataclass
class SubAgentRuntime:
    session: Session
    model: Model
    memory: Memory
    messages: list[dict[str, object]]
    mcp_url: str

    # Goal completed_tasks and reminaing_tasks are orchestrated from the main agent runtime

    # The goal of this step
    goal: str

    # So far what have we been able to do
    completed_tasks: list[TaskSchema]

    # So far what is remaining in the AI defined work flow and what work is remaining
    remaining_tasks: list[TaskSchema]

    # Stores every possible event that can occur
    event_ledger: list[EventSchema] = field(default_factory=list)

    # Stores the current world state
    world_state_ledger: list[WorldStateSchema] = field(default_factory=list) 
    # World states of what the agent has been seeing, we keep historical record, but for prompt contruction we only see the top one

    # Stores the objective goal and what we want to do to get there
    current_hypothesis: HypothesisSchema

    context_window_size: int = 20
    action_plan: PlanningExecuteActionSchema | None = None

    @property
    def observation_runtime(self) -> ObservationRuntime:
        return ObservationRuntime(
            model=self.model,
            messages=self.messages,
            mcp_url=self.mcp_url,
        )

    @property
    def planning_runtime(self) -> PlanningRuntime:
        return PlanningRuntime(
            model=self.model,
            messages=self.messages,
            on_action_planned=lambda action_plan: setattr(
                self, "action_plan", action_plan
            ),
        )

    @property
    def act_runtime(self) -> ActRuntime:
        return ActRuntime(
            messages=self.messages,
            mcp_url=self.mcp_url,
            timeout_seconds=self.timeout_seconds,
        )

    async def run_agent(self) -> None:
        while True:
            current_state = self.session.state
            if current_state.state is ExecuteLoopStateEnum.OBSERVE:
                decision = await self.observation_runtime.run_observation()

                if decision is ObservationStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.PLAN)
                elif decision in {
                    ObservationStatusEnum.BLOCKED,
                    ObservationStatusEnum.COMPLETE,
                }:
                    # For Now Return None, and we will think about it later,
                    # i was thinking probably we should add a decision here
                    # and also append to messages to show we are done here
                    # to the main loop

                    return
            elif current_state.state is ExecuteLoopStateEnum.PLAN:
                decision = await self.planning_runtime.run_planning()

                if decision is PlanningStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.ACT)
                elif decision is PlanningStatusEnum.BLOCKED:
                    return
            elif current_state.state is ExecuteLoopStateEnum.ACT:
                if self.action_plan is None:
                    raise RuntimeError("An action plan is required to act")

                status = await self.act_runtime.run_action(self.action_plan)

                if status in {
                    ToolCallStatusEnum.SUCCESS,
                    ToolCallStatusEnum.FAILED,
                    ToolCallStatusEnum.TIMED_OUT,
                }:
                    self.session.perform_transition(
                        ExecuteLoopStateEnum.OBSERVE
                    )
            else:
                raise ValueError("Unsupported State")
